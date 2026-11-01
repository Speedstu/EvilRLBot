from .action import Action
from .phys_obj import PhysObj
from .rot_mat import RotMat
from .team import Team
from .vec import Vec


class Player(PhysObj):
    def __init__(
        self, team=Team.BLUE, pos=Vec(), rot_mat=RotMat(), vel=Vec(), ang_vel=Vec()
    ):
        super().__init__(pos, rot_mat, vel, ang_vel)

        self.team = team
        self.index: int = -1

        self.is_on_ground = True
        self.is_jumping = False
        self.has_jumped = False
        self.is_flipping = False
        self.has_flipped = False
        self.has_double_jumped = False

        self.boost: float = 0.0
        self.is_demoed = False
        self.demo_respawn_timer = 0.0

        self.ball_touched_tick: bool = False
        self.ball_touched_step: bool = False

        self.handbrake_val: float = 0.0

        self.prev_action = Action()

        # Track air time since jump to match C++ HasFlipOrJump logic
        self.air_time_since_jump: float = 0.0

    def set_phys(self, phys: PhysObj):
        self.pos = phys.pos
        self.rot_mat = phys.rot_mat
        self.vel = phys.vel
        self.ang_vel = phys.ang_vel

    def has_flip_or_jump(self):
        # Mirror RLGC::CarState::HasFlipOrJump:
        # isOnGround OR (!hasFlipped && !hasDoubleJumped && airTimeSinceJump < DOUBLEJUMP_MAX_DELAY)
        return self.is_on_ground or (
            (not self.has_flipped)
            and (not self.has_double_jumped)
            and (self.air_time_since_jump < (1.25))  # RLConst.DOUBLEJUMP_MAX_DELAY
        )

    def has_flip_reset(self):
        return not self.is_on_ground and self.has_flip_or_jump() and not self.has_jumped

    # A bonus utility since we don't get this info from RLBot
    def is_probably_turtled(self):
        return (
            (not self.is_on_ground)
            and (self.rot_mat.up.z < -0.8)
            and (abs(self.vel.z) < 50)
            and (self.pos.z < 50)
        )
