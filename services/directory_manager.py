import os
from pathlib import Path


class DirectoryManager:
    """Manages directory creation and validation for the application"""

    REQUIRED_DIRS = {
        "output": {
            "track": "./output/track",
            "response_srt": "./output/response_srt",
            "cached_translations": "./output/cached_translations",
        }
    }

    @classmethod
    def ensure_all_directories(cls):
        """Creates all required directories if they don't exist"""
        for category, paths in cls.REQUIRED_DIRS.items():
            if isinstance(paths, dict):
                for subdir, path in paths.items():
                    Path(path).mkdir(parents=True, exist_ok=True)
            else:
                Path(paths).mkdir(parents=True, exist_ok=True)

    @classmethod
    def ensure_directory(cls, path):
        """Creates a specific directory if it doesn't exist"""
        Path(path).mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_path(cls, category, subdir=None):
        """Gets the full path for a directory category"""
        if subdir:
            return cls.REQUIRED_DIRS[category][subdir]
        return cls.REQUIRED_DIRS[category]
