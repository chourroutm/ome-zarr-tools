````markdown
name=README.md
# OME-Zarr Tools CLI

Command-line tools for working with OME-Zarr datasets.

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
    Extract images from a Zarr store.

- `fix_metadata`:
    Fix metadata in a Zarr store.

- `apply_mask`:
    Apply a mask file to a Zarr store.

- `config`:
    Show, set, or reset configuration.

## Development

To add more features or change options, see the Python files in `ome_zarr_tools/`.
````
