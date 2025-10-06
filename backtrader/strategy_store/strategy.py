"""enhanced version of the backtrader base Strategy class; intended to be used as a template for creating custom strategies"""

import logging
import numpy as np
import backtrader as bt

# TODO: refactor the portfolio realized volatility calculation
# TODO: add trading pause methods
# TODO: add basket trading function, to handle margin trading issues


class Position(object):
    def __init__(self, ticker: str, size: float, price: float) -> None:
        self._ticker = ticker
        self._size = size
        self._price = price

    @property
    def ticker(self) -> str:
        return self._ticker

    @property
    def size(self) -> float:
        return self._size

    @property
    def price(self) -> float:
        return self._price

    @property
    def value(self) -> float:
        return self._size * self._price


class StrategyMaster(bt.Strategy):

    # NOTE: naming rule, no leading "__" and trailing "__"
    params = (("parameter_grid", dict()),)

    def __init__(self, *args, **kwargs):
        """initialize the strategy"""
        super().__init__(*args, **kwargs)

    def next(self):
        pass

    def log(self, txt, dt=None, level="debug"):
        """Logging function fot this strategy"""
        dt = dt or self.datas[0].datetime.date(0)
        if level == "debug":
            logging.debug("%s: %s" % (dt.isoformat(), txt))
        elif level == "info":
            logging.info("%s: %s" % (dt.isoformat(), txt))
        elif level == "warning":
            logging.warning("%s: %s" % (dt.isoformat(), txt))
        elif level == "error":
            logging.error("%s: %s" % (dt.isoformat(), txt))
        elif level == "critical":
            logging.critical("%s: %s" % (dt.isoformat(), txt))
        else:
            # unrecognized logging level, set to info()
            logging.info("%s: %s" % (dt.isoformat(), txt))

    def notify_order(self, order):
        """optional, log the order status"""

        # handle orders which have not been handled
        if order.status in [order.Submitted, order.Accepted]:
            self.log(
                f"notify_order(): date: %s, order: %s, status: %s"
                % (self.dt(0).strftime("%Y%m%d"), order.data._name, order.getstatusname(order.status)),
            )
            return

        # check if an order has been completed
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            order_type = "BUY" if order.isbuy() else "SELL"
            msg = (
                f"{order_type} %s, ref:%.0f, Trade Date: %s, Price: %.2f, Cost: %.2f, Comm %.2f, Size: %.2f, Ticker: %s"
                % (
                    order.getstatusname(order.status),  # order status
                    order.ref,  # order id number
                    bt.num2date(order.executed.dt).strftime("%Y-%m-%d"),  # execution date
                    order.executed.price,  # execution price
                    order.executed.value,  # execution value
                    order.executed.comm,  # commission
                    order.executed.size,  # order size
                    order.data._name,  # instrument name
                )
            )
            self.log(msg)

    def getParameter(self, parameter: str, default=None):
        """get the parameter value from the parameter grid, if not found return the default value

        Parameters
        ----------
        parameter : str
            parameter name
        default : any, optional
            default value, by default None

        Returns
        -------
        any
            parameter value
        """
        grid = getattr(self.params, "parameter_grid", dict())
        return grid.get(parameter, default)

    def getOpenPosition(self, field: str = "close", ago: int = 0) -> dict[str, Position]:
        """get all open positions

        Parameters
        ----------
        field : str, optional
            field name, by default "close"
        ago : int, optional
            specify the index for the price, by default 0, for the current day

        Returns
        -------
        dict[str, Position]
            open positions
        """
        res = dict()
        for p, item in self.getpositions().items():
            if item.size != 0:
                data_ = self.getdatabyname(p._name)
                # raise error if field not in data feed
                if field not in data_._colmapping.keys():
                    raise ValueError(f"field {field} does not exist in the data feed")
                res[p._name] = Position(
                    p._name,
                    item.size,
                    getattr(data_, field).get(ago)[0],
                )

        return res

    def getPortfolioRealizedVol(self, look_back_periods: int) -> float:
        """get the portfolio realized volatility

        Parameters
        ----------
        look_back_periods : int
            the look back window

        Returns
        -------
        float
            annualized volatility
        """
        # ago = 0 for accessing the portfolio value is yesterday
        # len(self.stats.broker.value) != len(self.data)
        n_ = min(look_back_periods, len(self.stats.broker.value))
        total = np.array(self.stats.broker.value.get(0, n_), dtype=np.float32)
        # cash = np.array(self.stats.broker.cash.get(0, n_), dtype=np.float32)
        if n_ == 0:
            return 0.0
        if len(total) == 0:
            raise ValueError("portfolio value is empty ... look back period could be too long ...")
        if n_ < look_back_periods:
            self.log("getPortfolioRealizedVol(): data length shorter than the look back window", level="warning")
        rets = (
            np.divide(
                total,
                np.roll(total, 1),
                out=np.array([np.nan] * len(total)),
                where=np.roll(total, 1) != 0,
            )
            - 1
        )
        rets[0] = 0  # reset the 1st day return to 0.0
        if all(np.isnan(rets)):
            return 0.0
        return np.sqrt(np.sum(rets**2, where=~np.isnan(rets)) / sum((~np.isnan(rets))) * 252)  # annualized volatility
