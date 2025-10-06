"""define a collection of internal datafeed objects"""

from backtrader.feeds import PandasData


class CloseOnlyDatafeed(PandasData):
    """ """

    params = (
        # possible values for datetime (must always be present)
        #  None : datetime is the "index" in the Pandas Dataframe
        #  -1 : autodetect position or case-wise equal name
        #  >= 0 : numeric index to the colum in the pandas dataframe
        #  string : column name (as index) in the pandas dataframe
        ("datetime", None),
        # possible values below:
        #  None : column not present
        #  -1 : autodetect position or case-wise equal name
        #  >= 0 : numeric index to the colum in the pandas dataframe
        #  string : column name (as index) in the pandas dataframe
        ("open", None),
        ("high", None),
        ("low", None),
        ("close", -1),
        ("volume", None),
        ("openinterest", None),
    )
