import logging
import pandas as pd
import backtrader as bt
from backtrader.trade import Trade


# Analyzer for performance evaluation
class TradeAnalyzer(bt.Analyzer):

    def __init__(self):
        """initialize the trade analyzer"""
        self.open_trades = []
        self.close_trades = []
        self._trade_id = 0

    def notify_trade(self, trade: Trade):
        """Notify trade details to the analyzer"""
        # backtrader/strategy.py/Strategy._notify() method calls this method
        logging.debug("TradeAnalyzer: notify_trade() called: trade: %s", trade.ref)

        # NOTE: handle multiple open / close trades of the same position
        # https://www.backtrader.com/docu/trade/?h=trade
        try:

            # handle each trade individually, rather than handle the entire trade history
            self._handle_trade(trade)

            # if trade.isclosed:
            #     # when a position is closed, handle the entire trade history
            #     self._handle_trade_history(trade)
        except Exception as e:
            raise ValueError(f"Error processing trade {trade.ref}: {e}")

    def _handle_trade_history(self, trade: Trade):
        """Handle the entire trade history of a closed position

        parameters:
        ----------
        trade: backtrader.trade
            trade object to process
        """
        # NOTE: this parsing method is deprecated, as TradeAnalyzer will parse each trade individually
        # not the entire trade history of a closed position
        direction_ = None
        for trd in trade.history:
            # NOTE: trade.history is a list of backtrader.trade.TradeHistory objects
            # 2 attributes: "event" and "status"
            # event: odict_keys(['order', 'size', 'price', 'commission'])
            # status: odict_keys(['status', 'dt', 'barlen', 'size', 'price', 'value', 'pnl', 'pnlcomm', 'tz'])

            # action: if the trade direction is the same as the position direction then it is an open trade
            action_ = "open" if trd.event.size * (trd.status.size) > 0 else "close"

            # if after the trade, size = 0, then the direction should be the same as the last trade
            if trd.status.size != 0:
                direction_ = "long" if trd.status.size > 0 else "short"

            if direction_ is None:
                raise ValueError(f"Trade direction is not found for trade {trade.ref}")

            action_direction = f"{action_} {direction_}"
            ticker = trade.getdataname()
            ref_id = trade.ref  # backtrader, native reference id, unique for the entire liefspan of an open position
            exe_price = trd.event.price
            open_qty = trd.status.size
            exe_qty = trd.event.size
            # exe_date = bt.num2date(trd.status.dt).date()
            _status_dt = bt.num2date(trd.status.dt)
            exe_date = bt.num2date(trd.event.order.executed.dt)  # execution date of the trade
            trd_value = exe_price * exe_qty

            if action_ == "open":
                # handle open trades
                self.open_trades.append(
                    {
                        "ref_id": ref_id,
                        "trade_id": self._trade_id,
                        "ticker": ticker,
                        "action": action_direction,
                        "exe_date": exe_date,
                        "exe_price": exe_price,
                        "avg_cost": trd.status.price,  # the status.price has already been computed using average cost method
                        "exe_qty": exe_qty,
                        "open_qty": open_qty,
                        "trade_value": abs(trd_value),  # gross trade notional value
                        "commission": trd.event.commission,
                    }
                )
            else:
                nbars = trd.status.barlen
                # pnlcomm = trd.status.pnlcomm
                pnl = (trd.event.price - trd.status.price) * abs(trd.event.size)
                pnl = pnl if direction_ == "long" else -pnl
                pnl_percent = pnl / self.strategy.broker.getvalue()
                pnl_per_bar = pnl / nbars if nbars else 0

                # max and min prices during the trade period
                high_col = "close" if trade.data._colmapping.get("high") is None else "high"
                low_col = "close" if trade.data._colmapping.get("low") is None else "low"
                price_max = max(getattr(trade.data, high_col).get(ago=0, size=nbars + 1))
                price_min = min(getattr(trade.data, low_col).get(ago=0, size=nbars + 1))

                # maximum favorable and adverse excursions
                highest_price_change = price_max / trd.status.price - 1
                lowest_price_change = price_min / trd.status.price - 1

                mfp = highest_price_change if direction_ == "long" else -lowest_price_change
                mfl = lowest_price_change if direction_ == "long" else -highest_price_change

                # handle close trades, using average cost method
                self.close_trades.append(
                    {
                        "ref_id": ref_id,
                        "trade_id": self._trade_id,
                        "ticker": ticker,
                        "action": action_direction,
                        "avg_cost": trd.status.price,  # the status.price has already been computed using average cost method
                        "exe_date": exe_date,
                        "exe_price": exe_price,
                        "exe_qty": exe_qty,
                        "open_qty": open_qty,
                        "trade_value": abs(trd_value),  # gross trade notional value
                        "commission": trd.event.commission,
                        "chng%": exe_price / trd.status.price - 1,  # price change %: price close / price open - 1
                        "pnl": pnl,  # total price pnl excluding commission
                        "pnl%": pnl_percent,  # pnl / total portfolio value
                        "nbars": nbars,  # number of bars the trade was open
                        "pnl/bar": round(pnl_per_bar, 4),
                        "max_floatin_profit": round(mfp, 4),
                        "max_floating_loss": round(mfl, 4),
                    }
                )

            # keep track of the universal trade id
            self._trade_id += 1

    def get_analysis(self):
        """run the trade analysis"""
        open_trades = pd.DataFrame(self.open_trades)
        close_trades = pd.DataFrame(self.close_trades)
        trades = pd.concat([open_trades, close_trades], axis=0)
        if trades.empty:
            logging.warning("TradeAnalyzer: get_analysis(): trade: no trade records ...")
            return pd.DataFrame(
                columns=[
                    "ref_id",
                    "trade_id",
                    "ticker",
                    "action",
                    "exe_date",
                    "exe_price",
                    "avg_cost",
                    "exe_qty",
                    "open_qty",
                    "trade_value",
                    "commission",
                    "chng%",
                    "pnl",
                    "pnl%",
                    "nbars",
                    "pnl/bar",
                    "max_floatin_profit",
                    "max_floating_loss",
                ]
            )
        return trades.sort_values(by=["exe_date", "trade_id", "ticker"], ignore_index=True)

    def _handle_trade(self, trade: Trade):
        """parse latest trade object, which contains the latest event and status

        Parameters
        ----------
        trade : Trade
            backtrader.trade.Trade object
        """

        # 2 attributes: "event" and "status"
        # event: odict_keys(['order', 'size', 'price', 'commission'])
        # status: odict_keys(['status', 'dt', 'barlen', 'size', 'price', 'value', 'pnl', 'pnlcomm', 'tz'])

        ref_id = trade.ref  # backtrader, native reference id, unique for the entire liefspan of an open position
        direction_ = "long" if trade.long else "short"
        trd = trade.history[-1]  # get the latest trade object
        # action: if the trade direction is the same as the position direction then it is an open trade
        action_ = "open" if trd.event.size * (trd.status.size) > 0 else "close"

        # if after the trade, size = 0, then the direction should be the same as the last trade
        # if trd.status.size != 0:
        #     direction_ = "long" if trd.status.size > 0 else "short"
        # if direction_ is None:
        #     raise ValueError(f"Trade direction is not found for trade {trade.ref}")

        action_direction = f"{action_} {direction_}"
        ticker = trade.getdataname()
        ref_id = trade.ref  # backtrader, native reference id, unique for the entire liefspan of an open position
        exe_price, open_qty, exe_qty = trd.event.price, trd.status.size, trd.event.size
        # exe_date = bt.num2date(trd.status.dt).date()
        _status_dt = bt.num2date(trd.status.dt)
        exe_date = bt.num2date(trd.event.order.executed.dt)  # execution date of the trade
        trd_value = exe_price * exe_qty

        if action_ == "open":
            # handle open trades
            self.open_trades.append(
                {
                    "ref_id": ref_id,
                    "trade_id": self._trade_id,
                    "ticker": ticker,
                    "action": action_direction,
                    "exe_date": exe_date,
                    "exe_price": exe_price,
                    "avg_cost": trd.status.price,  # the status.price has already been computed using average cost method
                    "exe_qty": exe_qty,
                    "open_qty": open_qty,
                    "trade_value": abs(trd_value),  # gross trade notional value
                    "commission": trd.event.commission,
                }
            )
        else:
            nbars = trd.status.barlen
            # pnlcomm = trd.status.pnlcomm
            pnl = (trd.event.price - trd.status.price) * abs(trd.event.size)
            pnl = pnl if direction_ == "long" else -pnl
            pnl_percent = pnl / self.strategy.broker.getvalue()
            pnl_per_bar = pnl / nbars if nbars else 0

            # max and min prices during the trade period
            high_col = "close" if trade.data._colmapping.get("high") is None else "high"
            low_col = "close" if trade.data._colmapping.get("low") is None else "low"
            price_max = max(getattr(trade.data, high_col).get(ago=0, size=nbars + 1))
            price_min = min(getattr(trade.data, low_col).get(ago=0, size=nbars + 1))

            # maximum favorable and adverse excursions
            highest_price_change = price_max / trd.status.price - 1
            lowest_price_change = price_min / trd.status.price - 1

            mfp = highest_price_change if direction_ == "long" else -lowest_price_change
            mfl = lowest_price_change if direction_ == "long" else -highest_price_change

            # handle close trades, using average cost method
            self.close_trades.append(
                {
                    "ref_id": ref_id,
                    "trade_id": self._trade_id,
                    "ticker": ticker,
                    "action": action_direction,
                    "avg_cost": trd.status.price,  # the status.price has already been computed using average cost method
                    "exe_date": exe_date,
                    "exe_price": exe_price,
                    "exe_qty": exe_qty,
                    "open_qty": open_qty,
                    "trade_value": abs(trd_value),  # gross trade notional value
                    "commission": trd.event.commission,
                    "chng%": exe_price / trd.status.price - 1,  # price change %: price close / price open - 1
                    "pnl": pnl,  # total price pnl excluding commission
                    "pnl%": pnl_percent,  # pnl / total portfolio value
                    "nbars": nbars,  # number of bars the trade was open
                    "pnl/bar": round(pnl_per_bar, 4),
                    "max_floatin_profit": round(mfp, 4),
                    "max_floating_loss": round(mfl, 4),
                }
            )

        # keep track of the universal trade id
        # either "buy" or "sell" will be counted as a seperate trade
        self._trade_id += 1
