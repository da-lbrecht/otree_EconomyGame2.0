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
    market_opening='31 Mar 2022 07:00:00',
    market_closing='30 Apr 2022 18:00:00',
    currency_unit='&euro;',
    price_restrictions=True,
    price_floor=0,
    price_ceiling=100,
    taxation=True,
    seller_tax=0.1,
    buyer_tax=0.2,

    doc="")

# ISO-639 code
# for example: de, fr, ja, ko, zh-hans
LANGUAGE_CODE = 'en'

# e.g. EUR, GBP, CNY, JPY
REAL_WORLD_CURRENCY_CODE = 'USD'
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
    'trading_history',
    'previous_timestamp',
    'current_timestamp',
    'refresh_counter',
    'error',
]

SESSION_FIELDS = [
    'description',
]
