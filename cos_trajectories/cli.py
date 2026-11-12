"""Command-line interface: ``python -m cos_trajectories --help``.

Default folders are relative to the repository root (``01_COS``,
``03_Resultados``), as in the ArcGIS toolbox.
"""
import argparse
import logging
import sys
from pathlib import Path

from . import __version__, core
from .catalog import InputError

REPO_ROOT = Path(__file__).resolve().parents[1]


def build_parser():
    p = argparse.ArgumentParser(
        prog="python -m cos_trajectories",
        description="Land-use/land-cover history of sample points from the DGT COS series.",
    )
    p.add_argument("--cos-dir", default=str(REPO_ROOT / "01_COS"),
                   help="folder with the unzipped COS GeoPackages (default: %(default)s)")
    p.add_argument("--series", required=True, choices=["S1", "S2"],
                   help="COS series (Series 1 and Series 2 are not comparable; one per run)")
    p.add_argument("--samples", required=True, help="sample point layer (.shp or .gpkg)")
    p.add_argument("--samples-layer", default=None, help="layer name inside a GeoPackage")
    p.add_argument("--id-field", required=True, help="unique sample ID field")
    p.add_argument("--group-field", default=None, help="optional group field (e.g. quadrat)")
    p.add_argument("--level", type=int, default=None,
                   help="comparison level 1-4 (default: max level common to all editions)")
    p.add_argument("--threshold", type=float, default=core.DEFAULT_THRESHOLD_M,
                   help="boundary threshold in metres (default: %(default)s)")
    p.add_argument("--out-dir", default=str(REPO_ROOT / "03_Resultados"),
                   help="output folder; each run writes a subfolder (default: %(default)s)")
    p.add_argument("--run-id", default=None, help="name of the run subfolder (default: timestamp)")
    p.add_argument("--no-hash", action="store_true",
                   help="skip SHA-256 checksums of the COS files in the manifest (faster)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    logger = logging.getLogger("cos_trajectories")
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        res = core.run(
            cos_dir=args.cos_dir, series=args.series, samples_path=args.samples,
            samples_layer=args.samples_layer, id_field=args.id_field, group_field=args.group_field,
            level=args.level, boundary_threshold_m=args.threshold, out_dir=args.out_dir,
            run_id=args.run_id, with_hash=not args.no_hash,
        )
    except InputError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    finally:
        logger.removeHandler(handler)
    print(res.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
