from otree.api import *
import time
import random
import numpy as np


doc = "Double auction market"


class C(BaseConstants):
    NAME_IN_URL = 'double_auction'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1
    ITEMS_PER_SELLER = 3
    VALUATION_MIN = cu(50)
    VALUATION_MAX = cu(110)
    PRODUCTION_COSTS_MIN = cu(10)
    PRODUCTION_COSTS_MAX = cu(80)


class Subsession(BaseSubsession):
    pass


def creating_session(subsession: Subsession):
    players = subsession.get_players()
    for p in players:
        # this means if the player's ID is not a multiple of 2, they are a buyer.
        # for more buyers, change the 2 to 3
        p.is_buyer = p.id_in_group % 2 > 0
        participant = p.participant
        participant.offers = []
        if p.is_buyer:
            p.num_items = 0
            p.break_even_point = random.randint(C.VALUATION_MIN, C.VALUATION_MAX)
            p.current_offer = 0
        else:
            p.num_items = C.ITEMS_PER_SELLER
            p.break_even_point = random.randint(
                C.PRODUCTION_COSTS_MIN, C.PRODUCTION_COSTS_MAX
            )
            p.current_offer = C.VALUATION_MAX+1


class Group(BaseGroup):
    start_timestamp = models.IntegerField()


class Player(BasePlayer):
    is_buyer = models.BooleanField()
    offer = models.StringField()
    current_offer = models.CurrencyField()
    break_even_point = models.CurrencyField()
    num_items = models.IntegerField()

class Transaction(ExtraModel):
    group = models.Link(Group)
    buyer = models.Link(Player)
    seller = models.Link(Player)
    price = models.CurrencyField()
    seconds = models.IntegerField(doc="Timestamp (seconds since beginning of trading)")


def find_match(buyers, sellers):
    for buyer in buyers:
        for seller in sellers:
            if seller.num_items > 0 and seller.current_offer <= buyer.current_offer:
                # return as soon as we find a match (the rest of the loop will be skipped)
                return [buyer, seller]


def live_method(player: Player, data):
    group = player.group
    players = group.get_players()
    buyers = [p for p in players if p.is_buyer]
    sellers = [p for p in players if not p.is_buyer]
    news = None
    # offer = player.offer
    participant = player.participant
    offers = participant.offers
    if data:
        offers.append(int(data['offer']))
        participant.offers = offers
        # player.current_offer = offers[0]
        if player.is_buyer:
            offers.sort(reverse=True)  # Sort such that highest bid is first list element
            player.current_offer = offers[0]
            match = find_match(buyers=[player], sellers=sellers)
        else:
            offers.sort(reverse=False)  # Sort such that lowest ask is first list element
            player.current_offer = offers[0]
            match = find_match(buyers=buyers, sellers=[player])
        if match:
            [buyer, seller] = match
            price = buyer.current_offer
            Transaction.create(
                group=group,
                buyer=buyer,
                seller=seller,
                price=price,
                seconds=int(time.time() - time.mktime(time.strptime(player.session.config['market_opening'], "%d %b %Y %X"))),
            )
            buyer.num_items += 1
            seller.num_items -= 1
            buyer.payoff += buyer.break_even_point - price
            seller.payoff += price - seller.break_even_point
            news = dict(buyer=buyer.id_in_group, seller=seller.id_in_group, price=price)
            buyer.participant.offers = buyer.participant.offers[1:]
            seller.participant.offers = seller.participant.offers[1:]
            buyer.current_offer = buyer.participant.offers[0]
            seller.current_offer = seller.participant.offers[0]

    bids = sorted([p.current_offer for p in buyers if p.current_offer > 0], reverse=True)
    asks = sorted([p.current_offer for p in sellers if p.current_offer <= C.VALUATION_MAX])
    highcharts_series = [[tx.seconds, tx.price] for tx in Transaction.filter(group=group)]

    return {
        p.id_in_group: dict(
            num_items=p.num_items,
            current_offer=p.current_offer,
            payoff=p.payoff,
            bids=bids,
            asks=asks,
            highcharts_series=highcharts_series,
            news=news,
            offers=p.participant.offers,
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
        return dict(
            market_opening=market_opening,
            market_closing=market_closing,
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
