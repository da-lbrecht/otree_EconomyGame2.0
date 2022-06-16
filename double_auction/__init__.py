from otree.api import *
import time
from datetime import datetime
import numpy as np
import json  # Module to convert python dictionaries into JSON objects
import sys


def marginal_production_costs(t, min_mc, step):
    if t == 0:
        c = min_mc
    elif t <= 60:
        c = min_mc + 1 * step
    elif t <= 120:
        c = min_mc + 2 * step
    else:
        c = min_mc + 3 * step
    return c


def marginal_consumption_utility(t, max_mu, step):
    if t == 0:
        u = max_mu
    elif t <= 60:
        u = max_mu - 1 * step
    elif t <= 120:
        u = max_mu - 2 * step
    else:
        u = max_mu - 3 * step
    return u


# Define other general functions


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
    TIME_PER_UNIT = 60  # Time to produce/consume one unit is 1 minutes, i.e. 1*60=60 seconds
    # TIME_PER_UNIT = 600  # Time to produce/consume one unit is 10 minutes, i.e. 10*60=600 seconds
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
        session = subsession.session
        p.is_buyer = p.id_in_group % 2 > 0
        p.is_admin = p.id_in_group == 1  # The first participant link is for admin use only!!!
        p.balance = 0
        # Randomize costs and utility functions
        p.min_mc = int(np.random.randint(
            low=p.session.config['lower_bound_minimum_mc'],
            high=p.session.config['upper_bound_minimum_mc'],
            size=1, dtype=int
        )[0])
        p.max_mu = int(np.random.randint(
            low=p.session.config['lower_bound_maximum_mu'],
            high=p.session.config['upper_bound_maximum_mu'],
            size=1, dtype=int)[0])
        p.step_mu = p.session.config['mu_step_size']
        p.step_mc = p.session.config['mc_step_size']
        p.current_offer_time = C.MAX_TIMESTAMP
        # Inherit market parameters from session configs
        p.session_description = p.session.config['description']
        p.currency_unit = p.session.config['currency_unit']
        p.time_unit = p.session.config['time_unit']
        p.market_opening = p.session.config['market_opening']
        p.market_closing = p.session.config['market_closing']
        if p.is_buyer:
            p.current_offer = C.BID_MIN
            participant.marginal_evaluation = marginal_consumption_utility(0, p.max_mu, p.step_mu)
        else:
            p.current_offer = C.ASK_MAX
            participant.marginal_evaluation = marginal_production_costs(0, p.min_mc, p.step_mc)
        # Initialize participant variables
        participant.offers = []
        participant.offer_times = []
        participant.offer_history = []
        participant.trading_history = []
        participant.time_needed = 0
        participant.previous_timestamp = time.time()
        participant.current_timestamp = time.time()
        participant.error = None
        participant.news = None
        participant.notifications = []
        # Initialize session variables
        session.buyer_tax = round(float(p.session.config['buyer_tax']/100), 3)
        session.seller_tax = round(float(p.session.config['seller_tax']/100), 3)
        session.price_floor = round(p.session.config['price_floor'], 2)
        session.price_ceiling = round(p.session.config['price_ceiling'], 2)
        # Create data for MC/MU graphs
        cost_x = np.arange(0, 181, 1)
        cost_y = np.empty(shape=len(cost_x))
        for x in range(0, len(cost_x) - 1):
            cost_y[x] = marginal_production_costs(cost_x[x], p.min_mc, p.step_mc)
        participant.cost_chart_series = np.array((cost_x, cost_y)).T[:-1].tolist()

        utility_x = np.arange(0, 181, 1)
        utility_y = np.empty(shape=len(utility_x))
        for x in range(0, len(utility_x) - 1):
            utility_y[x] = marginal_consumption_utility(utility_x[x], p.max_mu, p.step_mu)
        participant.utility_chart_series = np.array((utility_x, utility_y)).T[:-1].tolist()


class Group(BaseGroup):
    start_timestamp = models.IntegerField()


class Player(BasePlayer):
    session_description = models.StringField()
    currency_unit = models.StringField()
    time_unit = models.StringField()
    market_opening = models.StringField()
    market_closing = models.StringField()
    is_admin = models.BooleanField()
    is_buyer = models.BooleanField()
    current_offer = models.FloatField()
    current_offer_time = models.FloatField()
    balance = models.FloatField()
    min_mc = models.FloatField()
    max_mu = models.FloatField()
    step_mc = models.FloatField()
    step_mu = models.FloatField()


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
    sellers = [p for p in players if not p.is_buyer and p.is_admin != 1]
    player.participant.news = None
    market_news = None
    # Details on market structure
    currency_unit = str(player.session.config['currency_unit'])
    seller_tax = float(player.subsession.session.seller_tax)
    buyer_tax = float(player.subsession.session.buyer_tax)
    price_floor = float(player.subsession.session.price_floor)
    price_ceiling = float(player.subsession.session.price_ceiling)
    # Details on participants
    participant = player.participant
    # offers = participant.offers
    offer_times = participant.offer_times  # List of tuples of offers and respective timestamp
    participant.error = None  # Empty all error messages
    if data:
        if data['type'] == 'offer':
            # Check if offer violates price restrictions
            if player.is_buyer \
                    and round(float(data['offer']), 2) < price_floor:
                player.participant.error = dict(
                    message="You are not allowed to bid below the price floor.",
                    time=str(datetime.today().ctime())
                )
                player.participant.notifications.append({"message": "You are not allowed to bid below the price floor.",
                                                         "time": str(datetime.today().ctime()),
                                                         "type": "error"})
            elif player.is_buyer == 0 \
                    and round(float(data['offer']), 2) > price_ceiling:
                player.participant.error = dict(
                    message="You are not allowed to ask above the price ceiling.",
                    time=str(datetime.today().ctime())
                )
                player.participant.notifications.append(
                    {"message": "You are not allowed to ask above the price ceiling.",
                     "time": str(datetime.today().ctime()),
                     "type": "error"})
            # Process offer
            else:
                offer_times.append((round(float(data['offer']), 2), datetime.today().timestamp()))
                if player.is_buyer:
                    offer_times.sort(key=lambda x: x[0],
                                     reverse=True)  # Sort such that highest bid is first list element
                    player.current_offer = offer_times[0][0]
                elif player.is_buyer == 0 and player.is_admin != 1:
                    offer_times.sort(key=lambda x: x[0],
                                     reverse=False)  # Sort such that lowest ask is first list element
                    player.current_offer = offer_times[0][0]
                participant.offer_times = offer_times
                player.current_offer_time = offer_times[0][1]
                # Search for matching offers
                if player.is_buyer:
                    match = find_match(buyers=[player], sellers=sellers)
                elif player.is_buyer == 0 and player.is_admin != 1:
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
                    if player.session.config['anonymity']:
                        buyer.participant.news = dict(
                            message="You bought one unit at price "
                                    + str('{:.2f}'.format((round(float(price), 2))))
                                    + " "
                                    + currency_unit,
                            time=str(datetime.today().ctime())
                        )
                        buyer.participant.notifications.append(
                            {"message": "You bought one unit at price "
                                        + str('{:.2f}'.format((round(float(price), 2))))
                                        + " "
                                        + currency_unit,
                             "time": str(datetime.today().ctime()),
                             "type": "news"})

                        seller.participant.news = dict(
                            message="You sold one unit at price "
                                    + str('{:.2f}'.format((round(float(price), 2))))
                                    + " "
                                    + currency_unit,
                            time=str(datetime.today().ctime())
                        )
                        seller.participant.notifications.append(
                            {"message": "You sold one unit at price "
                                        + str('{:.2f}'.format((round(float(price), 2))))
                                        + " "
                                        + currency_unit,
                             "time": str(datetime.today().ctime()),
                             "type": "news"})
                    else:
                        buyer.participant.news = dict(
                            message="You bought one unit at price "
                                    + str('{:.2f}'.format((round(float(price), 2))))
                                    + " "
                                    + currency_unit
                                    + " from Seller "
                                    + str(seller.id_in_group),
                            time=str(datetime.today().ctime())
                        )
                        buyer.participant.notifications.append(
                            {"message": "You bought one unit at price "
                                        + str('{:.2f}'.format((round(float(price), 2))))
                                        + " "
                                        + currency_unit
                                        + " from Seller "
                                        + str(seller.id_in_group),
                             "time": str(datetime.today().ctime()),
                             "type": "news"})

                        seller.participant.news = dict(
                            message="You sold one unit at price "
                                    + str('{:.2f}'.format((round(float(price), 2))))
                                    + " "
                                    + currency_unit
                                    + " to Buyer "
                                    + str(buyer.id_in_group),
                            time=str(datetime.today().ctime())
                        )
                        seller.participant.notifications.append(
                            {"message": "You sold one unit at price "
                                    + str('{:.2f}'.format((round(float(price), 2))))
                                    + " "
                                    + currency_unit
                                    + " to Buyer "
                                    + str(buyer.id_in_group),
                             "time": str(datetime.today().ctime()),
                             "type": "news"})

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
                        buyer.participant.offer_history.append({"offer": str('{:.2f}'.format(round(x[0], 2))) + " " +
                                                                         currency_unit,
                                                                "offer_time": datetime.fromtimestamp(x[1]).ctime()})
                    seller.participant.offer_history = []  # Empty offer history before recreating based on most recent info
                    for x in seller.participant.offer_times:
                        seller.participant.offer_history.append({"offer": str('{:.2f}'.format(round(x[0], 2))) + " " +
                                                                          currency_unit,
                                                                 "offer_time": datetime.fromtimestamp(x[1]).ctime()})
            # Update current offer history, i.e. standing offers after new offer has been made
            player.participant.offer_history = []  # Empty offer history before recreating based on most recent info
            for x in player.participant.offer_times:
                player.participant.offer_history.append({"offer": str('{:.2f}'.format(round(x[0], 2))) + " " +
                                                                  currency_unit,
                                                         "offer_time": datetime.fromtimestamp(x[1]).ctime()})
        elif data['type'] == 'withdrawal':
            withdrawal = data['withdrawal'].split(" ", 1)[0]
            if float(withdrawal) in [i[0] for i in offer_times]:
                del offer_times[([i[0] for i in offer_times]).index(float(withdrawal))]
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
            elif player.is_buyer == 0 and player.is_admin != 1:
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
                player.participant.offer_history.append({"offer": str('{:.2f}'.format(round(x[0], 2))) + " " +
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
                player.participant.marginal_evaluation = marginal_consumption_utility(player.participant.time_needed,
                                                                                      player.max_mu,
                                                                                      player.step_mu
                                                                                      )
            elif player.is_buyer == 0 and player.is_admin != 1:
                player.participant.marginal_evaluation = marginal_production_costs(player.participant.time_needed,
                                                                                   player.min_mc,
                                                                                   player.step_mc
                                                                                   )
        # Admin update of market structure
        elif data['type'] == 'market_update':
            # Check which parameters are updated
            new_market_params = [
                player.subsession.session.buyer_tax != round(float(data['buyer_tax_admin']) / 100, 3),
                player.subsession.session.seller_tax != round(float(data['seller_tax_admin']) / 100, 3),
                player.subsession.session.price_floor != round(float(data['price_floor_admin']), 2),
                player.subsession.session.price_ceiling != round(float(data['price_ceiling_admin']), 2)
            ]
            # Write updated parameters into session variable
            player.subsession.session.buyer_tax = round(float(data['buyer_tax_admin']) / 100, 3)
            player.subsession.session.seller_tax = round(float(data['seller_tax_admin']) / 100, 3)
            player.subsession.session.price_floor = round(float(data['price_floor_admin']), 2)
            player.subsession.session.price_ceiling = round(float(data['price_ceiling_admin']), 2)
            # Create message about market update
            if new_market_params == [False, False, False, False]:
                market_news = None
            else:
                if new_market_params == [True, False, False, False]:
                    market_news = dict(
                        message="A market intervention took place! The tax on buyers has changed to "
                                + str(round(float(data['buyer_tax_admin']), 1)) + " %.",
                        time=str(datetime.today().ctime()),
                        type="market_news"
                    )
                elif new_market_params == [False, True, False, False]:
                    market_news = dict(
                        message="A market intervention took place! The tax on sellers has changed to "
                                + str(round(float(data['seller_tax_admin']), 1)) + " %.",
                        time=str(datetime.today().ctime()),
                        type="market_news"
                    )
                elif new_market_params == [False, False, True, False]:
                    market_news = dict(
                        message="A market intervention took place! The price floor has changed to "
                                + str('{:.2f}'.format(round(float(data['price_floor_admin']), 2))) + " "
                                + str(player.session.config['currency_unit']) + ".",
                        time=str(datetime.today().ctime()),
                        type="market_news"
                    )
                elif new_market_params == [False, False, False, True]:
                    market_news = dict(
                        message="A market intervention took place! The price ceiling has changed to "
                                + str('{:.2f}'.format(round(float(data['price_ceiling_admin']), 2))) + " "
                                + str(player.session.config['currency_unit']) + ".",
                        time=str(datetime.today().ctime()),
                        type="market_news"
                    )
                elif new_market_params == [True, True, False, False]:
                    market_news = dict(
                        message="A market intervention took place! The tax on buyers has changed to "
                                + str(round(float(data['buyer_tax_admin']), 1))
                                + " % and the tax on sellers has changed to "
                                + str(round(float(data['seller_tax_admin']), 1)) + " %.",
                        time=str(datetime.today().ctime()),
                        type="market_news"
                    )
                elif new_market_params == [True, False, True, False]:
                    market_news = dict(
                        message="A market intervention took place! The tax on buyers has changed to "
                                + str(round(float(data['buyer_tax_admin']), 1))
                                + " % and the price floor has changed to "
                                + str('{:.2f}'.format(round(float(data['price_floor_admin']), 2))) + " "
                                + str(player.session.config['currency_unit']) + ".",
                        time=str(datetime.today().ctime()),
                        type="market_news"
                    )
                elif new_market_params == [True, False, False, True]:
                    market_news = dict(
                        message="A market intervention took place! The tax on buyers has changed to "
                                + str(round(float(data['buyer_tax_admin']), 1))
                                + " % and the price ceiling has changed to "
                                + str('{:.2f}'.format(round(float(data['price_ceiling_admin']), 2))) + " "
                                + str(player.session.config['currency_unit']) + ".",
                        time=str(datetime.today().ctime()),
                        type="market_news"
                    )
                elif new_market_params == [False, True, True, False]:
                    market_news = dict(
                        message="A market intervention took place! The tax on sellers has changed to "
                                + str(round(float(data['seller_tax_admin']), 1))
                                + " % and the price floor has changed to "
                                + str('{:.2f}'.format(round(float(data['price_floor_admin']), 2))) + " "
                                + str(player.session.config['currency_unit']) + ".",
                        time=str(datetime.today().ctime()),
                        type="market_news"
                    )
                elif new_market_params == [False, True, False, True]:
                    market_news = dict(
                        message="A market intervention took place! The tax on sellers has changed to "
                                + str(round(float(data['seller_tax_admin']), 1))
                                + " % and the price ceiling has changed to "
                                + str('{:.2f}'.format(round(float(data['price_ceiling_admin']), 2))) + " "
                                + str(player.session.config['currency_unit']) + ".",
                        time=str(datetime.today().ctime()),
                        type="market_news"
                    )
                elif new_market_params == [False, False, True, True]:
                    market_news = dict(
                        message="A market intervention took place! The price floor has changed to "
                                + str('{:.2f}'.format(round(float(data['price_floor_admin']), 2))) + " "
                                + str(player.session.config['currency_unit'])
                                + " and the price ceiling has changed to "
                                + str('{:.2f}'.format(round(float(data['price_ceiling_admin']), 2))) + " "
                                + str(player.session.config['currency_unit']) + ".",
                        time=str(datetime.today().ctime()),
                        type="market_news"
                    )
                elif new_market_params == [True, True, True, False]:
                    market_news = dict(
                        message="A market intervention took place! The tax on buyers has changed to "
                                + str(round(float(data['buyer_tax_admin']), 1))
                                + " %, the tax on sellers has changed to "
                                + str(round(float(data['seller_tax_admin']), 1))
                                + " % and the price floor has changed to "
                                + str('{:.2f}'.format(round(float(data['price_floor_admin']), 2))) + " "
                                + str(player.session.config['currency_unit']) + ".",
                        time=str(datetime.today().ctime()),
                        type="market_news"
                    )
                elif new_market_params == [True, False, True, True]:
                    market_news = dict(
                        message="A market intervention took place! The tax on buyers has changed to "
                                + str(round(float(data['buyer_tax_admin']), 1))
                                + " %, the price floor has changed to "
                                + str('{:.2f}'.format(round(float(data['price_floor_admin']), 2))) + " "
                                + str(player.session.config['currency_unit'])
                                + " and the price ceiling has changed to "
                                + str('{:.2f}'.format(round(float(data['price_ceiling_admin']), 2))) + " "
                                + str(player.session.config['currency_unit']) + ".",
                        time=str(datetime.today().ctime()),
                        type="market_news"
                    )
                elif new_market_params == [True, True, False, True]:
                    market_news = dict(
                        message="A market intervention took place! The tax on buyers has changed to "
                                + str(round(float(data['buyer_tax_admin']), 1))
                                + " %, the tax on sellers has changed to "
                                + str(round(float(data['seller_tax_admin']), 1))
                                + " % and the price ceiling has changed to "
                                + str('{:.2f}'.format(round(float(data['price_ceiling_admin']), 2))) + " "
                                + str(player.session.config['currency_unit']) + ".",
                        time=str(datetime.today().ctime()),
                        type="market_news"
                    )
                elif new_market_params == [False, True, True, True]:
                    market_news = dict(
                        message="A market intervention took place! The tax on sellers has changed to "
                                + str(round(float(data['seller_tax_admin']), 1))
                                + " %, the price floor has changed to "
                                + str('{:.2f}'.format(round(float(data['price_floor_admin']), 2))) + " "
                                + str(player.session.config['currency_unit'])
                                + " and the price ceiling has changed to "
                                + str('{:.2f}'.format(round(float(data['price_ceiling_admin']), 2))) + " "
                                + str(player.session.config['currency_unit']) + ".",
                        time=str(datetime.today().ctime()),
                        type="market_news"
                    )
                elif new_market_params == [True, True, True, True]:
                    market_news = dict(
                        message="A market intervention took place! The tax on buyers has changed to "
                                + str(round(float(data['buyer_tax_admin']), 11))
                                + " %, the tax on sellers has changed to "
                                + str(round(float(data['seller_tax_admin']), 1))
                                + " %, the price floor has changed to "
                                + str('{:.2f}'.format(round(float(data['price_floor_admin']), 2))) + " "
                                + str(player.session.config['currency_unit'])
                                + " and the price ceiling has changed to "
                                + str('{:.2f}'.format(round(float(data['price_ceiling_admin']), 2))) + " "
                                + str(player.session.config['currency_unit']) + ".",
                        time=str(datetime.today().ctime()),
                        type="market_news"
                    )
                else:
                    market_news = dict(
                        message="The market has been updated",
                        time=str(datetime.today().ctime()),
                        type="market_news"
                    )
                for p in players:
                    p.participant.notifications.append(market_news)
        elif data['type'] == 'notification_deletion':
            notifications = player.participant.notifications
            reversed_notifications = list(reversed(notifications))
            deletion = data['deletion']
            del reversed_notifications[deletion]
            notifications = list(reversed(reversed_notifications))
            player.participant.notifications = notifications

    # Create lists of all asks/bids by all sellers/buyers
    raw_bids = [[i[0] for i in p.participant.offer_times] for p in buyers]  # Collect bids from all buyers
    raw_bidders = [[p.id_in_group for i in p.participant.offer_times] for p in buyers]  # Collect bidders
    bids = flatten(raw_bids)  # Unnest list of bids
    bidders = flatten(raw_bidders)  # Unnest list of bidders
    # Dictionary of bid amount and bidder
    bid_keys = ["bid" for i in range(len(bids))]
    bidder_keys = ["bidder" for i in range(len(bidders))]
    overall_bids_dict_list = [[bid_keys[i], bids[i], bidder_keys[i], bidders[i]] for i in range(len(bids))]
    overall_bids = [
        {
            overall_bids_dict_list[i][0]: str('{:.2f}'.format(round(overall_bids_dict_list[i][1], 2))),
            overall_bids_dict_list[i][2]: overall_bids_dict_list[i][3]
        }
        for i in range(len(overall_bids_dict_list))
    ]
    bids.sort(reverse=True)

    # Collect asks from all sellers
    raw_asks = [[i[0] for i in p.participant.offer_times] for p in sellers]  # Collect asks from all sellers
    raw_askers = [[p.id_in_group for i in p.participant.offer_times] for p in sellers]  # Collect sellers
    asks = flatten(raw_asks)  # Unnest list
    askers = flatten(raw_askers)  # Unnest list of sellers
    # Dictionary of ask amount and asker
    ask_keys = ["ask" for i in range(len(asks))]
    asker_keys = ["asker" for i in range(len(askers))]
    overall_asks_dict_list = [[ask_keys[i], asks[i], asker_keys[i], askers[i]] for i in range(len(asks))]
    overall_asks = [
        {
            overall_asks_dict_list[i][0]: str('{:.2f}'.format(round(overall_asks_dict_list[i][1], 2))),
            overall_asks_dict_list[i][2]: overall_asks_dict_list[i][3]
        }
        for i in range(len(overall_asks_dict_list))
    ]
    asks.sort(reverse=False)

    return {
        p.id_in_group: dict(
            current_offer=str('{:.2f}'.format(round(p.current_offer, 2))) + " " + str(
                player.session.config['currency_unit']),
            current_offer_time=datetime.fromtimestamp(p.current_offer_time).ctime(),
            balance=str('{:.2f}'.format(round(p.balance, 2))) + " " + str(player.session.config['currency_unit']),
            bids=overall_bids,  # json.dumps(overall_bids_dict),
            asks=overall_asks,  # json.dumps(overall_asks_dict),
            cost_chart_series=p.participant.cost_chart_series,
            utility_chart_series=p.participant.utility_chart_series,
            chart_point=[[p.participant.time_needed, p.participant.marginal_evaluation]],
            offers=[str('{:.2f}'.format(round(i[0], 2))) for i in p.participant.offer_times],
            offer_times=[datetime.fromtimestamp(tup[1]).ctime() for tup in p.participant.offer_times],
            offer_history=p.participant.offer_history,  # json.dumps(dict(offers=p.participant.offer_history)),
            time_needed=p.participant.time_needed,
            marginal_evaluation=str('{:.2f}'.format(round(p.participant.marginal_evaluation, 2))) + " " + str(
                player.session.config['currency_unit']),
            trading_history=p.participant.trading_history,  # json.dumps(dict(trades=p.participant.trading_history)),
            buyer_tax=str('{:.1f}'.format(buyer_tax * 100)) + " " + str('%'),
            seller_tax=str('{:.1f}'.format(seller_tax * 100)) + " " + str('%'),
            price_floor=str('{:.2f}'.format(round(price_floor, 2))) + " " + str(
                player.session.config['currency_unit']),
            price_ceiling=str('{:.2f}'.format(round(price_ceiling, 2))) + " " + str(
                player.session.config['currency_unit']),
            buyer_tax_admin=buyer_tax * 100,
            seller_tax_admin=seller_tax * 100,
            price_floor_admin=round(price_floor, 2),
            price_ceiling_admin=round(price_ceiling, 2),
            currency_unit=currency_unit,
            time_unit=str(player.session.config['time_unit']),
            error=p.participant.error,
            market_news=market_news,
            news=p.participant.news,
            notifications=p.participant.notifications,
        )
        for p in players  # if p.is_admin is False
    }


# PAGES
class WaitToStart(Page):

    @staticmethod
    def is_displayed(player: Player):
        return time.time() < time.mktime(time.strptime(player.session.config['market_opening'], "%d %b %Y %X"))

    @staticmethod
    def get_timeout_seconds(player):
        return time.mktime(time.strptime(player.session.config['market_opening'], "%d %b %Y %X")) - time.time()

    @staticmethod
    def vars_for_template(player):
        return dict(
            title_text="The market is still closed until " + str(player.session.config['market_opening']),
            body_text="The market opening time is " + str(player.session.config['market_opening']))


class Trading(Page):
    live_method = live_method

    @staticmethod
    def get_timeout_seconds(player):
        return time.mktime(time.strptime(player.session.config['market_closing'], "%d %b %Y %X")) - time.time()

    @staticmethod
    def js_vars(player: Player):
        return dict(
            id_in_group=player.id_in_group,
            is_buyer=player.is_buyer,
            is_admin=player.is_admin,
            currency_unit=player.currency_unit,
            time_unit=player.time_unit
        )

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
        return dict(
            market_opening=player.session.config['market_opening'],
            market_closing=player.session.config['market_closing'],
        )

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        player.payoff = player.balance


class Results(Page):

    @staticmethod
    def is_displayed(player: Player):
        return time.time() > time.mktime(time.strptime(player.session.config['market_closing'], "%d %b %Y %X"))

    @staticmethod
    def vars_for_template(player):
        return dict(
            title_text="The market has closed at " + str(player.session.config['market_closing']),
            body_text="Your final profit is "
                      + str('{:.2f}'.format(round(player.balance, 2)))
                      + " " + str(player.session.config['currency_unit'])
        )


page_sequence = [
    WaitToStart,
    Trading,
    Results
]


def custom_export(players):
    yield ['session', 'description', 'buyer', 'seller', 'price', 'seconds',
           'buyer_valuation', 'seller_costs', 'buyer_profits', 'seller_profits', 'buyer_balance', 'seller_balance',
           'seller_tax', 'buyer_tax', 'price_floor', 'price_ceiling']
    for p in players:
        for tx in Transaction.filter(seller=p):
            yield [p.session.code, tx.description, tx.buyer.id_in_group, tx.seller.id_in_group, tx.price, tx.seconds,
                   tx.buyer_valuation, tx.seller_costs, tx.buyer_profits, tx.seller_profits, tx.buyer_balance,
                   tx.seller_balance, tx.seller_tax, tx.buyer_tax, tx.price_floor, tx.price_ceiling]
