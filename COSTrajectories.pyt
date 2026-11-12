# -*- coding: utf-8 -*-
"""ArcGIS Pro toolbox: thin wrapper around the ``cos_trajectories`` package.

arcpy is used only here: parameter handling, messages and adding the result
to the map. The processing runs in a separate Python process of the active
ArcGIS Pro environment (``python -m cos_trajectories``), not inside the
ArcGIS Pro application:

- the GDAL/PROJ libraries used by geopandas/fiona are not loaded into the
  ArcGIS Pro process, where they can conflict with the application's own
  copies and terminate it;
- every run uses the code currently on disk (ArcGIS Pro keeps imported
  modules in memory for the whole session).

The package is found through the folder of this .pyt; no installation needed.
"""
import os
import re
import subprocess
import sys

import arcpy

HERE = os.path.dirname(os.path.abspath(__file__))
SERIES = ["S1", "S2", "S1+S2"]  # S1+S2: both series merged in one trajectory
DEFAULT_THRESHOLD_M = 25.0


def _version():
    try:
        with open(os.path.join(HERE, "cos_trajectories", "__init__.py"), encoding="utf-8") as f:
            return re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)
    except Exception:  # noqa: BLE001 - label only
        return "?"


def _python_exe():
    """python.exe of the active environment (sys.executable is ArcGISPro.exe inside the application)."""
    for cand in (os.path.join(sys.exec_prefix, "python.exe"), sys.executable):
        if cand and os.path.isfile(cand) and os.path.basename(cand).lower().startswith("python"):
            return cand
    raise RuntimeError(f"python.exe not found in the active environment ({sys.exec_prefix})")


def _data_source(value):
    """(path, layer) of a feature layer or dataset parameter value; shapefile or GeoPackage only."""
    path = arcpy.Describe(value).catalogPath
    low = path.lower()
    if ".gpkg" in low:
        i = low.index(".gpkg") + len(".gpkg")
        gpkg, layer = path[:i], path[i:].lstrip("\\/")
        if layer.lower().startswith("main."):
            layer = layer[5:]
        return gpkg, layer or None
    if low.endswith(".shp"):
        return path, None
    raise ValueError(f"sample layer must be a shapefile or a GeoPackage layer, got {path}. "
                     "Export it to one of these formats first.")


class Toolbox:
    def __init__(self):
        self.label = "COS Trajectories"
        self.alias = "costraj"
        self.tools = [CosTrajectories]


class CosTrajectories:
    def __init__(self):
        self.label = "COS land-use history of sample points"
        self.description = (
            "Extracts the DGT COS class of each sample point in every edition of one COS series, "
            "with trajectory, stability metrics, boundary flags, transition matrices, a manifest "
            f"and a data dictionary. cos_trajectories {_version()}."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        cos_dir = arcpy.Parameter(displayName="COS folder (unzipped GeoPackages)", name="cos_dir",
                                  datatype="DEFolder", parameterType="Required", direction="Input")
        cos_dir.value = os.path.join(HERE, "01_COS")
        series = arcpy.Parameter(displayName="COS series", name="series", datatype="GPString",
                                 parameterType="Required", direction="Input")
        series.filter.type = "ValueList"
        series.filter.list = SERIES
        series.value = "S1"
        samples = arcpy.Parameter(displayName="Sample points", name="samples", datatype="GPFeatureLayer",
                                  parameterType="Required", direction="Input")
        samples.filter.list = ["Point", "Multipoint"]
        id_field = arcpy.Parameter(displayName="Sample ID field (unique)", name="id_field", datatype="Field",
                                   parameterType="Required", direction="Input")
        id_field.parameterDependencies = [samples.name]
        group_field = arcpy.Parameter(displayName="Group field (optional)", name="group_field",
                                      datatype="Field", parameterType="Optional", direction="Input")
        group_field.parameterDependencies = [samples.name]
        level = arcpy.Parameter(displayName="Comparison level (empty = most detailed common level)",
                                name="level", datatype="GPLong", parameterType="Optional", direction="Input")
        level.filter.type = "ValueList"
        level.filter.list = [1, 2, 3, 4]
        threshold = arcpy.Parameter(displayName="Boundary threshold (m)", name="threshold",
                                    datatype="GPDouble", parameterType="Required", direction="Input")
        threshold.value = DEFAULT_THRESHOLD_M
        out_dir = arcpy.Parameter(displayName="Output folder (a subfolder is created per run)", name="out_dir",
                                  datatype="DEFolder", parameterType="Required", direction="Input")
        out_dir.value = os.path.join(HERE, "03_Resultados")
        add_map = arcpy.Parameter(displayName="Add result to the current map", name="add_to_map",
                                  datatype="GPBoolean", parameterType="Optional", direction="Input")
        add_map.value = True
        result = arcpy.Parameter(displayName="Run folder", name="result", datatype="DEFolder",
                                 parameterType="Derived", direction="Output")
        return [cos_dir, series, samples, id_field, group_field, level, threshold, out_dir, add_map, result]

    def isLicensed(self):
        return True

    def updateMessages(self, parameters):
        thr = parameters[6]
        if thr.value is not None and thr.value < 0:
            thr.setErrorMessage("The threshold must be zero or positive.")
        samples = parameters[2]
        if samples.value is not None:
            try:
                _data_source(samples.valueAsText)
            except Exception as e:  # noqa: BLE001 - shown to the user
                samples.setErrorMessage(str(e))

    def execute(self, parameters, messages):
        p = {x.name: x for x in parameters}
        try:
            samples_path, samples_layer = _data_source(p["samples"].valueAsText)
            python = _python_exe()
        except Exception as e:  # noqa: BLE001 - shown to the user
            arcpy.AddError(str(e))
            return
        try:
            if getattr(arcpy.Describe(p["samples"].value), "FIDSet", ""):
                arcpy.AddWarning("The sample layer has a selection; all features of the data source "
                                 "are processed.")
        except Exception:  # noqa: BLE001 - informative only
            pass

        cmd = [python, "-m", "cos_trajectories",
               "--cos-dir", p["cos_dir"].valueAsText, "--series", p["series"].valueAsText,
               "--samples", samples_path, "--id-field", p["id_field"].valueAsText,
               "--threshold", repr(float(p["threshold"].value)), "--out-dir", p["out_dir"].valueAsText]
        if samples_layer:
            cmd += ["--samples-layer", samples_layer]
        if p["group_field"].valueAsText:
            cmd += ["--group-field", p["group_field"].valueAsText]
        if p["level"].value is not None:
            cmd += ["--level", str(int(p["level"].value))]

        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        proc = subprocess.Popen(cmd, cwd=HERE, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace",
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        run_dir, tail = None, []
        try:
            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                if line.startswith("INFO "):
                    arcpy.AddMessage(line[5:])
                elif line.startswith("WARNING "):
                    arcpy.AddWarning(line[8:])
                elif line.startswith("ERROR"):
                    arcpy.AddError(line.split(" ", 1)[1] if " " in line else line)
                else:
                    tail.append(line)
                    if os.path.isdir(line):
                        run_dir = line
            code = proc.wait()
        finally:
            if proc.poll() is None:
                proc.kill()
        if code != 0 or run_dir is None:
            if code != 2:  # 2 = input error, already reported; anything else is unexpected
                arcpy.AddError(f"cos_trajectories ended with code {code}.\n" + "\n".join(tail[-25:]))
            return

        p["result"].value = run_dir
        arcpy.AddMessage(f"Results: {run_dir}")
        if p["add_to_map"].value:
            try:
                m = arcpy.mp.ArcGISProject("CURRENT").activeMap
                if m is not None:
                    m.addDataFromPath(os.path.join(run_dir, "samples_cos_history.gpkg",
                                                   "main.samples_cos_history"))
            except Exception as e:  # noqa: BLE001 - no open project (e.g. run from Python)
                arcpy.AddMessage(f"Result not added to a map ({e}).")
