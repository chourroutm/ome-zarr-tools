# OME-Zarr Tools CLI

Command-line tools for working with OME-Zarr multiscale datasets (also known as OME-NGFF). It is currently designed for [the OME-Zarr 0.4 specifications](https://ngff.openmicroscopy.org/0.4/index.html).

## Installation

Install via pip (make sure you have all runtime dependencies):
```bash
pip install .
```

## Usage

```bash
ome-zarr-tools [subcommand] [OPTIONS]
```

### Subcommands

- `from_images`:
    Convert from a stack of 2D images or a 3D image file.
    Options:
      --stack_dir, --stack_files, --stack_pattern, --vol_file
      --voxel_size, --voxel_size_unit, --axis_order

- `extract`:
    Extract images from an OME-Zarr multiscale dataset.

- `fix_metadata`:
    Fix metadata in an OME-Zarr multiscale dataset.

- `apply_mask`:
    Apply a mask file to an OME-Zarr multiscale dataset.

- `config`:
    Show, set, or reset configuration.

## Development

To add more features or change options, see the Python files in `ome_zarr_tools/`.
