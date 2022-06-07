import sys
import os
import os.path


def get_datafile(filename: str) -> str:
    """
    Get the filename for a data file within in module.
    """

    # if getattr(sys, "frozen", False):
    #     # The application is frozen with cx_Freeze
    #     directory: str = os.path.dirname(sys.executable)
    # else:
    directory: str = os.path.dirname(__file__)
    return os.path.join(directory, filename)
