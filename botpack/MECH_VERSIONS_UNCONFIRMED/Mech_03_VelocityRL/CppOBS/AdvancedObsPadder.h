#pragma once

#include <RLGymCPP/ObsBuilders/ObsBuilder.h>
#include <RLGymCPP/Gamestates/StateUtil.h>
#include <RLGymCPP/CommonValues.h> // For constants
#include <algorithm>               // For std::shuffle

namespace RLGC {
    // A comprehensive observation builder that includes a wide variety of information
    // from the game state, including previous states for temporal context.
    class ComprehensiveObs : public ObsBuilder {
    public:
        // Coefficients for normalizing physical values
        const float POS_COEF;
        const float VEL_COEF;
        const float ANG_VEL_COEF;

        // Maximum number of players the observation supports (for padding)
        int maxPlayers;

        ComprehensiveObs(int maxPlayers = 6);

        // Appends a player's information to the observation list
        void AddPlayerToObs(FList& obs, const Player& player, const GameState& state, bool inverted);

        // Builds the full observation for a specific player
        virtual FList BuildObs(const Player& player, const GameState& state) override;
    };
}