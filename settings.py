from os import environ

SESSION_CONFIGS = [
    dict(
        name='double_auction',
        display_name="Double auction market",
        app_sequence=['double_auction'],
        num_demo_participants=4,
    ),
]

# if you set a property in SESSION_CONFIG_DEFAULTS, it will be inherited by all configs
# in SESSION_CONFIGS, except those that explicitly override it.
# the session config can be accessed from methods in your apps as self.session.config,
# e.g. self.session.config['participation_fee']

SESSION_CONFIG_DEFAULTS = dict(
    description='Economy Game 2.0',
    real_world_currency_per_point=1.00,
    participation_fee=0.00,
    market_opening='01 Aug 2022 09:00:00',
    market_closing='30 Aug 2023 18:00:00',
    currency_unit='&euro;',
    buyer_share=2,
    # time_unit='seconds',
    price_floor=0.00,
    price_ceiling=1000.00,
    seller_tax=0.0,
    buyer_tax=0.0,
    anonymity=True,
    # target_equilibrium_price=60,
    lower_bound_minimum_mc=20,
    upper_bound_minimum_mc=59,
    lower_bound_maximum_mu=61,
    upper_bound_maximum_mu=100,
    mc_step_size=25,
    mu_step_size=25,
    production_time=60,
    consumption_time=60,
    doc="")

# ISO-639 code
# for example: de, fr, ja, ko, zh-hans
LANGUAGE_CODE = 'en'

# e.g. EUR, GBP, CNY, JPY
REAL_WORLD_CURRENCY_CODE = 'EUR'
USE_POINTS = True

ADMIN_USERNAME = 'admin'
# for security, best to set admin password in an environment variable
ADMIN_PASSWORD = environ.get('OTREE_ADMIN_PASSWORD')

DEMO_PAGE_INTRO_HTML = """ """
DEMO_PAGE_TITLE = "Economy Game 2.0"

SECRET_KEY = '4387860144726'

# if an app is included in SESSION_CONFIGS, you don't need to list it here
INSTALLED_APPS = ['otree']

PARTICIPANT_FIELDS = [
    'offers',
    'offer_times',
    'offer_history',
    'time_needed',
    'marginal_evaluation',
    'cost_chart_series',
    'utility_chart_series',
    'trading_history',
    'previous_timestamp',
    'current_timestamp',
    'refresh_counter',
    'error',
    'news',
    'notifications'
]

SESSION_FIELDS = [
    'description',
    'buyer_tax',
    'seller_tax',
    'price_floor',
    'price_ceiling'
]
