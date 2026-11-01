from .vec import Vec

TICK_TIME = 1 / 120

GRAVITY = Vec(0.0, 0.0, -650.0)

SIDE_WALL_X = 4096.0
BACK_WALL_Y = 5120.0
CEILING_Z = 2044.0
BACK_NET_Y = 6000
CORNER_WALL_AX_INTERSECT = 8064

GOAL_HEIGHT = 642.775
GOAL_WIDTH_FROM_CENTER = 892.755
ORANGE_GOAL_CENTER = Vec(0.0, BACK_WALL_Y, GOAL_HEIGHT / 2)
BLUE_GOAL_CENTER = Vec(0.0, -BACK_WALL_Y, GOAL_HEIGHT / 2)

BALL_RADIUS = 91.25
BALL_RESTITUTION = 0.6

CAR_MAX_SPEED = 2300.0
CAR_MAX_THROTTLE_SPEED = 1410
CAR_MAX_ANG_VEL = 5.5
BOOST_ACCELERATION = 991.66

BOOST_LOCATIONS_AMOUNT = 34
BOOST_LOCATIONS = [
    Vec(0.0, -4240.0, 70.0),
    Vec(-1792.0, -4184.0, 70.0),
    Vec(1792.0, -4184.0, 70.0),
    Vec(-3072.0, -4096.0, 73.0),
    Vec(3072.0, -4096.0, 73.0),
    Vec(-940.0, -3308.0, 70.0),
    Vec(940.0, -3308.0, 70.0),
    Vec(0.0, -2816.0, 70.0),
    Vec(-3584.0, -2484.0, 70.0),
    Vec(3584.0, -2484.0, 70.0),
    Vec(-1788.0, -2300.0, 70.0),
    Vec(1788.0, -2300.0, 70.0),
    Vec(-2048.0, -1036.0, 70.0),
    Vec(2048.0, -1036.0, 70.0),
    Vec(0.0, -1024.0, 70.0),
    Vec(-3584.0, 0.0, 73.0),
    Vec(-1024.0, 0.0, 70.0),
    Vec(1024.0, 0.0, 70.0),
    Vec(3584.0, 0.0, 73.0),
    Vec(0.0, 1024.0, 70.0),
    Vec(-2048.0, 1036.0, 70.0),
    Vec(2048.0, 1036.0, 70.0),
    Vec(-1788.0, 2300.0, 70.0),
    Vec(1788.0, 2300.0, 70.0),
    Vec(-3584.0, 2484.0, 70.0),
    Vec(3584.0, 2484.0, 70.0),
    Vec(0.0, 2816.0, 70.0),
    Vec(-940.0, 3310.0, 70.0),
    Vec(940.0, 3308.0, 70.0),
    Vec(-3072.0, 4096.0, 73.0),
    Vec(3072.0, 4096.0, 73.0),
    Vec(-1792.0, 4184.0, 70.0),
    Vec(1792.0, 4184.0, 70.0),
    Vec(0.0, 4240.0, 70.0),
]

MIRRORED_PAD_MAPPING = list(map(lambda x: x[0], sorted(enumerate(BOOST_LOCATIONS), key=lambda x: x[1].y * 10000 - x[1].x)))

DEMO_RESPAWN_TIME = 3.0