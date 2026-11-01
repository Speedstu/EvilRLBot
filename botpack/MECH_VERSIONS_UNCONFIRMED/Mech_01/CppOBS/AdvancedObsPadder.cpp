#include "AdvancedObsPadder.h" // Assumes this is in the same directory as your other obs builders

using namespace RLGC;

ComprehensiveObs::ComprehensiveObs(int maxPlayers) :
    maxPlayers(maxPlayers),
    POS_COEF(1.0f / CommonValues::BACK_WALL_Y),
    VEL_COEF(1.0f / CommonValues::CAR_MAX_SPEED),
    ANG_VEL_COEF(1.0f / CommonValues::CAR_MAX_ANG_VEL) {
}

void ComprehensiveObs::AddPlayerToObs(FList& obs, const Player& player, const GameState& state, bool inverted) {
    PhysState phys = InvertPhys(player, inverted);
    PhysState ballPhys = InvertPhys(state.ball, inverted);

    obs.reserve(obs.size() + 40); // Pre-allocate to avoid multiple reallocations

    // Player Physics
    obs += phys.pos * POS_COEF;
    obs += phys.rotMat.forward;
    obs += phys.rotMat.up;
    obs += phys.vel * VEL_COEF;
    obs += phys.angVel * ANG_VEL_COEF;

    // Player State Booleans
    obs += static_cast<float>(player.isOnGround);
    obs += static_cast<float>(player.hasJumped);
    obs += static_cast<float>(player.hasDoubleJumped);
    obs += static_cast<float>(player.hasFlipped);
    obs += static_cast<float>(player.isFlipping);
    obs += static_cast<float>(player.isSupersonic);
    obs += static_cast<float>(player.isDemoed);
    obs += static_cast<float>(player.ballTouchedStep);

    // Other Player Info
    obs += player.boost / 100.0f;
    obs += player.airTime;

    // Relative Ball Info
    obs += phys.rotMat.Dot(ballPhys.pos - phys.pos) * POS_COEF;
    obs += phys.rotMat.Dot(ballPhys.vel - phys.vel) * VEL_COEF;

    // Previous State Info (if available)
    if (player.prev) {
        PhysState prevPhys = InvertPhys(*player.prev, inverted);
        obs += (phys.pos - prevPhys.pos) * POS_COEF; // Positional delta
        obs += (phys.vel - prevPhys.vel) * VEL_COEF; // Acceleration
    }
    else {
        // If no previous state, pad with zeros
        for (int i = 0; i < 6; ++i) obs.push_back(0.f);
    }
}

FList ComprehensiveObs::BuildObs(const Player& player, const GameState& state) {
    FList obs = {};
    obs.reserve(300); // Pre-allocate a reasonable amount

    bool inverted = (player.team == Team::ORANGE);

    // Ball Physics
    PhysState ballPhys = InvertPhys(state.ball, inverted);
    obs += ballPhys.pos * POS_COEF;
    obs += ballPhys.vel * VEL_COEF;
    obs += ballPhys.angVel * ANG_VEL_COEF;

    // Previous Ball Physics (if available)
    if (state.prev) {
        PhysState prevBallPhys = InvertPhys(state.prev->ball, inverted);
        obs += prevBallPhys.pos * POS_COEF;
        obs += prevBallPhys.vel * VEL_COEF;
        obs += prevBallPhys.angVel * ANG_VEL_COEF;
    }
    else {
        for (int i = 0; i < 9; ++i) obs.push_back(0.f);
    }

    // Boost Pad States & Timers
    const auto& pads = state.GetBoostPads(inverted);
    for (bool pad_state : pads) obs.push_back(static_cast<float>(pad_state));

    const auto& pad_timers = state.GetBoostPadTimers(inverted);
    obs.insert(obs.end(), pad_timers.begin(), pad_timers.end());

    // Player's previous action
    for (float val : player.prevAction) {
        obs.push_back(val);
    }

    // Add self to observation
    FList selfObs;
    AddPlayerToObs(selfObs, player, state, inverted);
    obs.insert(obs.end(), selfObs.begin(), selfObs.end());
    int playerObsSize = selfObs.size();

    // Prepare lists for teammates and opponents
    std::vector<FList> teammates, opponents;
    for (const auto& otherPlayer : state.players) {
        if (otherPlayer.carId == player.carId) continue;

        FList otherObs;
        AddPlayerToObs(otherObs, otherPlayer, state, inverted);

        if (otherPlayer.team == player.team) {
            teammates.push_back(otherObs);
        }
        else {
            opponents.push_back(otherObs);
        }
    }

    // Pad and add other players to the observation
    int numTeammates = teammates.size();
    int numOpponents = opponents.size();

    while (teammates.size() < (size_t)maxPlayers - 1) {
        teammates.push_back(FList(playerObsSize, 0.f));
    }

    while (opponents.size() < (size_t)maxPlayers) {
        opponents.push_back(FList(playerObsSize, 0.f));
    }

    // Shuffle to prevent positional bias
    std::shuffle(teammates.begin(), teammates.begin() + numTeammates, RocketSim::Math::GetRandEngine());
    std::shuffle(opponents.begin(), opponents.begin() + numOpponents, RocketSim::Math::GetRandEngine());

    for (const auto& teammateObs : teammates) {
        obs.insert(obs.end(), teammateObs.begin(), teammateObs.end());
    }

    for (const auto& opponentObs : opponents) {
        obs.insert(obs.end(), opponentObs.begin(), opponentObs.end());
    }

    return obs;
}