"""position analyzer, to store the time series information of """

from typing import Dict
import backtrader as bt
import pandas as pd


class PerformanceAnalyzer(bt.Analyzer):

    def __init__(self):
        self.position = dict()
        self.value = dict()

    def next(self):

        # iterate through all the items
        dt = self.datas[0].datetime.datetime(0).strftime("%Y-%m-%d %H:%M:%S")
        position = {dt: dict()}
        value = {dt: dict()}

        for item in self.strategy.datas:
            position_item = self.strategy.getpositionbyname(item._name)
            position[dt].update({item._name: position_item.size})
            value[dt].update({item._name: position_item.size * item.close[0]})

        # get cash seperately
        position[dt].update({"MNYFUND": self.strategy.broker.get_cash()})
        value[dt].update({"MNYFUND": self.strategy.broker.get_cash()})

        self.position.update(position)
        self.value.update(value)

    def get_analysis(self) -> Dict[str, pd.DataFrame]:
        """return the analysis results of the performance"""

        position = pd.DataFrame.from_dict(self.position, orient="index")
        position.index = pd.to_datetime(position.index)
        position.index.name = "datetime"
        value = pd.DataFrame.from_dict(self.value, orient="index")
        value.index = pd.to_datetime(value.index)
        value.index.name = "datetime"
        wgt = value.copy(deep=True)
        wgt = wgt.div(value.sum(axis=1), axis=0).fillna(0)

        # portfolio total value, daily pnl and daily return
        portfolio = value.sum(axis=1).to_frame(name="total_value")
        portfolio["daily_pnl"] = (portfolio["total_value"] - portfolio["total_value"].shift(1)).fillna(0)
        portfolio["daily_return"] = portfolio["total_value"].pct_change().fillna(0)

        # return the analysis results
        # position_qty: time series of position quantity
        # position_value: time series of position value
        # position_wgt: time series of position weight
        return {
            "position_qty": position,
            "position_value": value,
            "position_wgt": wgt,
            "performance": portfolio,
        }
