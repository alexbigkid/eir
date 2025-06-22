#!/usr/bin/env python3
"""Setup script to populate the mixed date range test directory."""

import shutil
from pathlib import Path


def setup_mixed_directory():
    """Set up the mixed date range directory with files from all other directories."""
    test_images_dir = Path(__file__).parent.parent / "test_images"
    mixed_dir = test_images_dir / "20110709-20230809_img_unsorted"

    # Clear existing mixed directory
    if mixed_dir.exists():
        shutil.rmtree(mixed_dir)
    mixed_dir.mkdir(parents=True, exist_ok=True)

    # Copy files from all individual date directories
    source_dirs = [
        "20110709_canon",
        "20211218_sony",
        "20221231_iPhone_raw",
        "20230808_sony",
        "20230809_Canon_R8",
        "20230809_Fujifilm_X-S20",
        "20230809_Leica_Q3",
        "20230809_Sony_a6700",
    ]

    copied_count = 0
    for source_dir_name in source_dirs:
        source_dir = test_images_dir / source_dir_name
        if source_dir.exists():
            print(f"Copying files from {source_dir_name}...")
            for file_path in source_dir.iterdir():
                if file_path.is_file():
                    dest_path = mixed_dir / file_path.name
                    # Handle name collisions by adding suffix
                    counter = 1
                    while dest_path.exists():
                        stem = file_path.stem
                        suffix = file_path.suffix
                        dest_path = mixed_dir / f"{stem}_{counter:02d}{suffix}"
                        counter += 1

                    shutil.copy2(file_path, dest_path)
                    copied_count += 1
                    print(f"  Copied: {file_path.name} -> {dest_path.name}")

    print("\n✅ Mixed directory setup complete!")
    print(f"📁 Directory: {mixed_dir}")
    print(f"📄 Total files copied: {copied_count}")

    # List final contents
    files = list(mixed_dir.glob("*"))
    print("📋 Files in mixed directory:")
    for file_path in sorted(files):
        if file_path.is_file():
            print(f"  - {file_path.name}")


if __name__ == "__main__":
    setup_mixed_directory()
