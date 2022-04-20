from otree.api import *
import time
from datetime import datetime
import numpy as np
import json  # Module to convert python dictionaries into JSON objects
import sys

##### START: Definition of production costs and consumption utilities #####

# Production Costs with production facilities of different efficiency p_eff_1, ..., p_eff_5, and corresponding
# capacities p_cap_1, ..., p_cap_2
p_eff_1 = 25
p_eff_2 = 50
p_eff_3 = 100
p_eff_4 = 200
p_eff_5 = 400
p_cap_1 = 600  # Any capacity needs to ne at least C.TIME_PER_UNIT
p_cap_2 = 600
p_cap_3 = 600
p_cap_4 = 600
p_cap_5 = 600


def marginal_production_costs(t):
    c = round((max((600 - t), 0) * 50 + (600 - max(600 - t, 0)) * 100) / 600, 2)
    return c


def marginal_consumption_utility(t):
    u = round((max((600 - t), 0) * 100 + (600 - max(600 - t, 0)) * 50) / 600, 2)
    return u


# Graphs


cost_x = np.arange(0, 1810, 10)
cost_y = np.empty(shape=len(cost_x))
for x in range(0, len(cost_x) - 1):
    cost_y[x] = marginal_production_costs(cost_x[x])
cost_chart_series = np.array((cost_x, cost_y)).T[:-1].tolist()

utility_x = np.arange(0, 1810, 10)
utility_y = np.empty(shape=len(utility_x))
for x in range(0, len(utility_x) - 1):
    utility_y[x] = marginal_consumption_utility(utility_x[x])
utility_chart_series = np.array((utility_x, utility_y)).T[:-1].tolist()


##### END: Definition of production costs and consumption utilities #####


# Further Functions

def flatten(list_of_lists):  # Python function to unlist lists
    if len(list_of_lists) == 0:
        return list_of_lists
    if isinstance(list_of_lists[0], list):
        return flatten(list_of_lists[0]) + flatten(list_of_lists[1:])
    return list_of_lists[:1] + flatten(list_of_lists[1:])


doc = "Double auction market"


class C(BaseConstants):
    NAME_IN_URL = 'double_auction'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1
    BID_MIN = -sys.maxsize
    ASK_MAX = sys.maxsize
    TIME_PER_UNIT = 600  # Time to produce/consume one unit is 10 minutes, i.e. 10*60=600 seconds
    MIN_TIMESTAMP = datetime(2000, 1, 1, 0, 0, 0, 0).timestamp()
    MAX_TIMESTAMP = datetime(3001, 1, 1, 0, 0, 0, 0).timestamp()


class Subsession(BaseSubsession):
    pass


def creating_session(subsession: Subsession):
    players = subsession.get_players()
    for p in players:
        # this means if the player's ID is not a multiple of 2, they are a buyer.
        # for more buyers, change the 2 to 3
        participant = p.participant
        p.is_buyer = p.id_in_group % 2 > 0
        p.balance = 0
        p.session_description = p.session.config['description']
        p.current_offer_time = C.MAX_TIMESTAMP
        if p.is_buyer:
            p.current_offer = C.BID_MIN
            participant.marginal_evaluation = marginal_consumption_utility(0)
        else:
            p.current_offer = C.ASK_MAX
            participant.marginal_evaluation = marginal_production_costs(0)
        # Initialize participant variables
        participant.offers = []
        participant.offer_times = []
        participant.offer_history = []
        participant.trading_history = []
        participant.time_needed = 0
        participant.previous_timestamp = time.time()
        participant.current_timestamp = time.time()
        participant.refresh_counter = 0
        participant.error = ""


class Group(BaseGroup):
    start_timestamp = models.IntegerField()


class Player(BasePlayer):
    session_description = models.StringField()
    is_buyer = models.BooleanField()
    current_offer = models.FloatField()
    current_offer_time = models.FloatField()
    balance = models.FloatField()


class Transaction(ExtraModel):
    group = models.Link(Group)
    buyer = models.Link(Player)
    seller = models.Link(Player)
    price = models.FloatField(doc="Price of this trade, excl. any taxes, i.e. amount of money exchanged between buyer"
                                  " and seller")
    buyer_valuation = models.FloatField(doc="Buyer's valuation of the item purchased (i.e. marginal utility)")
    seller_costs = models.FloatField(doc="Seller's production cost of the item purchased (i.e. marginal costs)")
    buyer_profits = models.FloatField(doc="Buyer's profit from this trade (if <0 then loss)")
    seller_profits = models.FloatField(doc="Seller's profit from this trade (if <0 then loss)")
    buyer_balance = models.FloatField(doc="Buyer's new balance after this trade")
    seller_balance = models.FloatField(doc="Seller's new balance after this trade")
    seconds = models.IntegerField(doc="Timestamp (seconds since market opening)")
    description = models.StringField(doc="Description/Name of the Market given by experimenter")
    buyer_tax = models.FloatField(doc="Buyers paid this share of the trading price in taxes")
    seller_tax = models.FloatField(doc="Sellers paid this share of the trading price in taxes.")
    price_floor = models.FloatField(doc="Buyers are not allowed to bid lower than the price floor.")
    price_ceiling = models.FloatField(doc="Sellers are not allowed to ask higher than the price ceiling.")


def find_match(buyers, sellers):
    for buyer in buyers:
        for seller in sellers:
            if seller.current_offer <= buyer.current_offer:
                # return as soon as we find a match (the rest of the loop will be skipped)
                return [buyer, seller]


def live_method(player: Player, data):
    group = player.group
    players = group.get_players()
    buyers = [p for p in players if p.is_buyer]
    sellers = [p for p in players if not p.is_buyer]
    news = None
    # Details on market structure
    currency_unit = str(player.session.config['currency_unit'])
    if player.session.config['taxation']:
        seller_tax = float(player.session.config['seller_tax'])
        buyer_tax = float(player.session.config['buyer_tax'])
    else:
        seller_tax = 0
        buyer_tax = 0
    if player.session.config['price_restrictions']:
        price_floor = player.session.config['price_floor']
        price_ceiling = player.session.config['price_ceiling']
    else:
        price_floor = None
        price_ceiling = None
    # Details on participants
    participant = player.participant
    # offers = participant.offers
    offer_times = participant.offer_times  # List of tuples of offers and respective timestamp
    participant.error = None  # Empty all error messages
    if data:
        if data['type'] == 'offer':
            if player.session.config['price_restrictions'] \
                    and player.is_buyer \
                    and float(data['offer']) < int(player.session.config['price_floor']):
                player.participant.error = "You are not allowed to bid below the price floor."
            elif player.session.config['price_restrictions'] \
                    and player.is_buyer == 0 \
                    and float(data['offer']) > int(player.session.config['price_ceiling']):
                player.participant.error = "You are not allowed to ask above the price ceiling."
            else:
                # offers.append(float(data['offer']))
                # participant.offers = offers
                offer_times.append((float(data['offer']), datetime.today().timestamp()))
                if player.is_buyer:
                    offer_times.sort(key=lambda x: x[0],
                                     reverse=True)  # Sort such that highest bid is first list element
                    player.current_offer = offer_times[0][0]
                else:
                    offer_times.sort(key=lambda x: x[0],
                                     reverse=False)  # Sort such that lowest ask is first list element
                    player.current_offer = offer_times[0][0]
                participant.offer_times = offer_times
                player.current_offer_time = offer_times[0][1]
                if player.is_buyer:
                    match = find_match(buyers=[player], sellers=sellers)
                else:
                    match = find_match(buyers=buyers, sellers=[player])
                if match:
                    [buyer, seller] = match
                    if buyer.current_offer_time < seller.current_offer_time:
                        price = buyer.current_offer
                    else:
                        price = seller.current_offer
                    buyer_trading_history = buyer.participant.trading_history
                    seller_trading_history = seller.participant.trading_history
                    trade_time = str(datetime.today().ctime())
                    Transaction.create(
                        description=player.session.config['description'],
                        group=group,
                        buyer=buyer,
                        seller=seller,
                        price=price,
                        seconds=int(time.time() - time.mktime(
                            time.strptime(player.session.config['market_opening'], "%d %b %Y %X"))),
                        buyer_valuation=buyer.participant.marginal_evaluation,
                        seller_costs=seller.participant.marginal_evaluation,
                        buyer_profits=buyer.participant.marginal_evaluation - price - (buyer_tax * price),
                        seller_profits=price - seller.participant.marginal_evaluation - (seller_tax * price),
                        buyer_balance=buyer.balance + buyer.participant.marginal_evaluation - price - (
                                buyer_tax * price),
                        seller_balance=seller.balance + price - seller.participant.marginal_evaluation - (
                                seller_tax * price),
                        buyer_tax=buyer_tax,
                        seller_tax=seller_tax,
                        price_floor=price_floor,
                        price_ceiling=price_ceiling,
                    )
                    # Calculate new balances
                    buyer.balance += buyer.participant.marginal_evaluation - price - (buyer_tax * price)
                    seller.balance += price - seller.participant.marginal_evaluation - (seller_tax * price)
                    # Create message about effected trade
                    news = dict(buyer=buyer.id_in_group, seller=seller.id_in_group, price=price, time=trade_time)
                    # Delete bids/asks of effected trade from bid/ask cue
                    buyer.participant.offer_times = buyer.participant.offer_times[1:]
                    seller.participant.offer_times = seller.participant.offer_times[1:]
                    if len(buyer.participant.offer_times) >= 1:
                        buyer.current_offer = buyer.participant.offer_times[0][0]
                        buyer.current_offer_time = buyer.participant.offer_times[0][1]
                    else:
                        buyer.current_offer = C.BID_MIN
                        buyer.current_offer_time = C.MAX_TIMESTAMP
                    if len(seller.participant.offer_times) >= 1:
                        seller.current_offer = seller.participant.offer_times[0][0]
                        seller.current_offer_time = seller.participant.offer_times[0][1]
                    else:
                        seller.current_offer = C.ASK_MAX
                        seller.current_offer_time = C.MAX_TIMESTAMP
                    # Trading history
                    buyer_trading_history.insert(0, {"price": str('{:.2f}'.format((round(float(price), 2)))) + " "
                                                              + currency_unit,
                                                     "time": trade_time,
                                                     "tax_on_buyer": str(buyer_tax * 100) + " %",
                                                     "tax_on_seller": str(seller_tax * 100) + " %",
                                                     "price_floor": str('{:.2f}'.format(round(price_floor, 2))) + " "
                                                                    + currency_unit,
                                                     "price_ceiling": str('{:.2f}'.format(round(price_ceiling, 2)))
                                                                      + " " + currency_unit,
                                                     "profit_from_trade": str('{:.2f}'.format(round(
                                                         buyer.participant.marginal_evaluation - price -
                                                         (buyer_tax * price), 2))) + " " + currency_unit,
                                                     }),
                    buyer.participant.trading_history = buyer_trading_history
                    seller_trading_history.insert(0, {"price": str('{:.2f}'.format(round(float(price), 2))) + " "
                                                               + currency_unit,
                                                      "time": trade_time,
                                                      "tax_on_buyer": str(buyer_tax * 100) + " %",
                                                      "tax_on_seller": str(seller_tax * 100) + " %",
                                                      "price_floor": str('{:.2f}'.format(round(price_floor, 2))) + " "
                                                                     + currency_unit,
                                                      "price_ceiling": str('{:.2f}'.format(round(price_ceiling, 2)))
                                                                       + " " + currency_unit,
                                                      "profit_from_trade": str('{:.2f}'.format(round(
                                                          price - seller.participant.marginal_evaluation -
                                                          (seller_tax * price), 2))) + " " + currency_unit,
                                                      }),
                    seller.participant.trading_history = seller_trading_history
                    # Update remaining time needed for production/consumption
                    buyer.participant.time_needed += C.TIME_PER_UNIT
                    seller.participant.time_needed += C.TIME_PER_UNIT
                    # Update current offer history, i.e. still standing offers after trade
                    buyer.participant.offer_history = []  # Empty offer history before recreating based on most recent info
                    for x in buyer.participant.offer_times:
                        buyer.participant.offer_history.append({"offer": str('{:.2f}'.format(round(x[0]))) + " " +
                                                                         currency_unit,
                                                                 "offer_time": datetime.fromtimestamp(x[1]).ctime()})
                    seller.participant.offer_history = []  # Empty offer history before recreating based on most recent info
                    for x in seller.participant.offer_times:
                        seller.participant.offer_history.append({"offer": str('{:.2f}'.format(round(x[0]))) + " " +
                                                                          currency_unit,
                                                                 "offer_time": datetime.fromtimestamp(x[1]).ctime()})
            # Update current offer history, i.e. standing offers after new offer has been made
            player.participant.offer_history = []  # Empty offer history before recreating based on most recent info
            for x in player.participant.offer_times:
                player.participant.offer_history.append({"offer": str('{:.2f}'.format(round(x[0]))) + " " +
                                                                  currency_unit,
                                                         "offer_time": datetime.fromtimestamp(x[1]).ctime()})
        elif data['type'] == 'withdrawal':
            withdrawal = data['withdrawal'].split(" ", 1)[0]
            if float(withdrawal) in [i[0] for i in offer_times]:
                del offer_times[([i[0] for i in offer_times]).index(float(data['withdrawal']))]
                # offer_times = [x for x in offer_times if x[0] in offers]
            # participant.offers = offers
            participant.offer_times = offer_times
            if player.is_buyer:
                offer_times.sort(key=lambda x: x[0], reverse=True)  # Sort such that highest bid is first list element
                if len(offer_times) >= 1:
                    player.current_offer = offer_times[0][0]
                    player.current_offer_time = offer_times[0][1]
                else:
                    player.current_offer = C.BID_MIN
                    player.current_offer_time = C.MAX_TIMESTAMP
            else:
                offer_times.sort(key=lambda x: x[0], reverse=False)  # Sort such that lowest ask is first list element
                if len(offer_times) >= 1:
                    player.current_offer = offer_times[0][0]
                    player.current_offer_time = offer_times[0][1]
                else:
                    player.current_offer = C.ASK_MAX
                    player.current_offer_time = C.MAX_TIMESTAMP
            # Current offer history, i.e. still standing offers
            player.participant.offer_history = []  # Empty offer history before recreating based on most recent info
            for x in player.participant.offer_times:
                player.participant.offer_history.append({"offer": str('{:.2f}'.format(round(x[0]))) + " " +
                                                                  currency_unit,
                                                         "offer_time": datetime.fromtimestamp(x[1]).ctime()})
        elif data['type'] == 'time_update':
            # Update remaining time needed for production/consumption
            player.participant.current_timestamp = time.time()
            player.participant.time_needed = round(max(0, player.participant.time_needed -
                                                       (player.participant.current_timestamp -
                                                        player.participant.previous_timestamp)), 0)
            player.participant.previous_timestamp = player.participant.current_timestamp
            # Update marginal utility/costs
            if player.is_buyer:
                player.participant.marginal_evaluation = marginal_consumption_utility(player.participant.time_needed)
            else:
                player.participant.marginal_evaluation = marginal_production_costs(player.participant.time_needed)
            # Update refresh counter
            if player.participant.refresh_counter == 10:
                player.participant.refresh_counter = 0
            else:
                player.participant.refresh_counter += 1

    # Create lists of all asks/bids by all sellers/buyers
    raw_bids = [[i[0] for i in p.participant.offer_times] for p in buyers]  # Collect bids from all buyers
    raw_bidders = [[p.id_in_group for i in p.participant.offer_times] for p in buyers]  # Collect bidders
    bids = flatten(raw_bids)  # Unnest list of bids
    bidders = flatten(raw_bidders)  # Unnest list of bidders
    bids_index = [i for i in range(len(bids))]
    bids_dict = dict(zip(bids_index, bids))  # Dictionary of bid index and bid amount
    bidders_dict = dict(zip(bids_index, bidders))  # Dictionary of bid index and bidder.id_in_group
    # bidders_dict = dict(zip(bids_index, [bool(x == player.id_in_group) for x in bidders]))
    bids.sort(reverse=True)

    # Collect asks from all sellers
    raw_asks = [[i[0] for i in p.participant.offer_times] for p in sellers]  # Collect asks from all sellers
    raw_askers = [[p.id_in_group for i in p.participant.offer_times] for p in sellers]  # Collect sellers
    asks = flatten(raw_asks)  # Unnest list
    askers = flatten(raw_askers)  # Unnest list of sellers
    asks_index = [i for i in range(len(asks))]
    asks_dict = dict(zip(asks_index, asks))  # Dictionary of ask index and ask amount
    askers_dict = dict(zip(asks_index, askers))  # Dictionary of bid index and bidder.id_in_group
    asks.sort(reverse=False)

    # Create charts
    highcharts_series = [[tx.seconds, tx.price] for tx in Transaction.filter(group=group)]
    return {
        p.id_in_group: dict(
            current_offer=str('{:.2f}'.format(round(p.current_offer, 2))) + " " + str(
                player.session.config['currency_unit']),
            current_offer_time=datetime.fromtimestamp(p.current_offer_time).ctime(),
            balance=str('{:.2f}'.format(round(p.balance, 2))) + " " + str(player.session.config['currency_unit']),
            bids=[str('{:.2f}'.format(round(x, 2))) for x in bids],
            # Create a dictionaries of offers with an offer index, offer amount and player.id_in_group
            bids_dict=json.dumps(dict(bid=bids_dict, bidder=bidders_dict)),
            asks=[str('{:.2f}'.format(round(x, 2))) for x in asks],
            asks_dict=json.dumps(dict(ask=asks_dict, asker=askers_dict)),
            highcharts_series=highcharts_series,
            cost_chart_series=cost_chart_series,
            chart_point=[[p.participant.time_needed, p.participant.marginal_evaluation]],
            utility_chart_series=utility_chart_series,
            news=news,
            offers=[str('{:.2f}'.format(round(i[0], 2))) for i in p.participant.offer_times],
            offer_times=[datetime.fromtimestamp(tup[1]).ctime() for tup in p.participant.offer_times],
            offer_history=json.dumps(dict(offers=p.participant.offer_history)),
            time_needed=p.participant.time_needed,
            marginal_evaluation=str('{:.2f}'.format(round(p.participant.marginal_evaluation, 2))) + " " + str(
                player.session.config['currency_unit']),
            trading_history=json.dumps(dict(trades=p.participant.trading_history)),
            refresh_counter=p.participant.refresh_counter,
            error=p.participant.error,
        )
        for p in players
    }


# PAGES
class WaitToStart(WaitPage):
    @staticmethod
    def after_all_players_arrive(group: Group):
        group.start_timestamp = int(time.time())


class Trading(Page):
    live_method = live_method

    @staticmethod
    def js_vars(player: Player):
        return dict(id_in_group=player.id_in_group, is_buyer=player.is_buyer)

    @staticmethod
    def get_timeout_seconds(player: Player):
        import time

        group = player.group
        market_opening_timestamp = time.mktime(time.strptime(player.session.config['market_opening'], "%d %b %Y %X"))
        group.start_timestamp = int(market_opening_timestamp)
        market_closing_timestamp = time.mktime(time.strptime(player.session.config['market_closing'], "%d %b %Y %X"))
        # return (group.start_timestamp + 5 * 60) - time.time()
        return market_closing_timestamp - time.time()

    @staticmethod
    def vars_for_template(player: Player):
        market_opening = player.session.config['market_opening']
        market_closing = player.session.config['market_closing']
        currency_unit = player.session.config['currency_unit']
        if player.session.config['price_restrictions']:
            price_floor_display = player.session.config['price_floor']
            price_ceiling_display = player.session.config['price_ceiling']
        else:
            price_floor_display = "-"
            price_ceiling_display = "-"
        if player.session.config['taxation']:
            taxation = True
            seller_tax_display = player.session.config['seller_tax'] * 100
            buyer_tax_display = player.session.config['buyer_tax'] * 100
        else:
            taxation = False
            seller_tax_display = 0
            buyer_tax_display = 0
        return dict(
            market_opening=market_opening,
            market_closing=market_closing,
            price_floor=str('{:.2f}'.format(round(price_floor_display, 2))) + " " + str(
                player.session.config['currency_unit']),
            price_ceiling=str('{:.2f}'.format(round(price_ceiling_display))) + " " + str(
                player.session.config['currency_unit']),
            taxation=taxation,
            seller_tax=seller_tax_display,
            buyer_tax=buyer_tax_display,
        )


class ResultsWaitPage(WaitPage):
    pass


class Results(Page):
    pass


page_sequence = [
    # WaitToStart,
    Trading,
    ResultsWaitPage,
    Results
]


# def custom_export(players):
#     yield ['balance']
#     for p in players:
#         yield [p.balance]


def custom_export(players):
    yield ['session', 'description', 'buyer', 'seller', 'price', 'seconds',
           'buyer_valuation', 'seller_costs', 'buyer_profits', 'seller_profits', 'buyer_balance', 'seller_balance',
           'seller_tax', 'buyer_tax', 'price_floor', 'price_ceiling']
    for p in players:
        for tx in Transaction.filter(seller=p):
            yield [p.session.code, tx.description, tx.buyer.id_in_group, tx.seller.id_in_group, tx.price, tx.seconds,
                   tx.buyer_valuation, tx.seller_costs, tx.buyer_profits, tx.seller_profits, tx.buyer_balance,
                   tx.seller_balance, tx.seller_tax, tx.buyer_tax, tx.price_floor, tx.price_ceiling]
