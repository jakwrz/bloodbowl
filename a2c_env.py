import numpy as np
from botbowl import OutcomeType, Game
import botbowl.core.procedure as procedure
from implementation.scripted_bot import CustomScriptedBot
import botbowl.core.pathfinding as pathfinding_module


class A2C_Reward:
    env_size = 11
    POSITIVE_MULTIPLER = 1.2
    BALL_PROGRESSION_REWARD = 0.006
    CHANCE_WEIGHT = 0.5
    TACKLE_ZONE_REWARD = 0.0001
    TACKLE_ZONE_BALL_FAR_RANGE = 3
    TACKLE_ZONE_BALL_WEIGHT = 8
    TACKLE_ZONE_BALL_CLOSE_RANGE_WEIGHT = 5
    TACKLE_ZONE_BALL_FAR_RANGE_WEIGHT = 2
    CONTROL_BALL_REWARD = 0.00002
    TOUCHDOWN_PATH_REWARD = 0.00001
    TOUCHDOWN_CLEAR_PATH_WEIGHT = 5
    PICKUP_TO_ENDZONE_PATH_REWARD = 0.004
    DOUBLE_BLOCK_BONUS = 0.5

    OWN_REPORT_REWARDS = {
        OutcomeType.TOUCHDOWN: 4,
        OutcomeType.SUCCESSFUL_CATCH: 0.2,
        OutcomeType.INTERCEPTION: 0.4,
        OutcomeType.SUCCESSFUL_PICKUP: 0.2,
        OutcomeType.FUMBLE: -0.2,
        OutcomeType.KNOCKED_DOWN: -0.2,
        OutcomeType.KNOCKED_OUT: -0.4,
        OutcomeType.CASUALTY: -1
    }
    OPP_REPORT_REWARDS = {
        OutcomeType.TOUCHDOWN: -3,
        OutcomeType.SUCCESSFUL_CATCH: -0.2,
        OutcomeType.INTERCEPTION: -0.4,
        OutcomeType.SUCCESSFUL_PICKUP: -0.2,
        OutcomeType.FUMBLE: 0.2,
        OutcomeType.KNOCKED_DOWN: 0.2,
        OutcomeType.KNOCKED_OUT: 0.4,
        OutcomeType.CASUALTY: 1
    }

    def __init__(self):
        self.last_report_idx = 0
        self.last_ball_x = None
        self.last_ball_team = None
        self.control_ball_reward = 0
        self.my_team = None
        self.opp_team = None

    def __call__(self, game: Game):
        self.my_team = game.active_team
        self.opp_team = game.get_opp_team(self.my_team)
        if len(game.state.reports) < self.last_report_idx:
            self.last_report_idx = 0
        report_reward = self.calculate_report_rewards(game)
        ball_progression_reward = self.calculate_ball_progression_reward(game)
        tackle_zones_reward = self.calculate_tackle_zones_reward(game)
        control_ball_reward = self.calculate_control_ball_reward(game)
        path_to_touchdown_reward = self.calculate_path_to_touchdown_reward(game)
        ball_pickup_reward = self.calculate_ball_pickup_reward(game)

        return report_reward + ball_progression_reward  + tackle_zones_reward + control_ball_reward + \
            path_to_touchdown_reward + ball_pickup_reward

    def _positive_multiply(self, reward):
        return reward if reward <= 0 else reward * self.POSITIVE_MULTIPLER

    def calculate_report_rewards(self, game: Game):
        reward = 0.0
        for outcome in game.state.reports[self.last_report_idx:]:
            team = outcome.player.team if outcome.player else outcome.team
            reward_dict = self.OWN_REPORT_REWARDS if team == self.my_team else self.OPP_REPORT_REWARDS
            chance = self._get_outcome_chance(outcome)
            weighted_chance = (chance * self.CHANCE_WEIGHT + 1 - self.CHANCE_WEIGHT) * self.CHANCE_WEIGHT
            reward += reward_dict.get(outcome.outcome_type, 0) * weighted_chance
        self.last_report_idx = len(game.state.reports)
        return reward

    def _get_outcome_chance(self, outcome):
        chance = 1
        if outcome.rolls is not []:
            for roll in outcome.rolls:
                if roll.target is not None:
                    chance *= roll.get_details()['chance']
        return chance

    def calculate_ball_progression_reward(self, game: Game):
        reward = 0.0
        ball_carrier = game.get_ball_carrier()
        if ball_carrier is not None:
            if self._has_ball(game):
                ball_progress = self.last_ball_x - ball_carrier.position.x
                if self.my_team == game.state.away_team:
                    ball_progress *= -1
                reward += self.BALL_PROGRESSION_REWARD * ball_progress
            self.last_ball_team = ball_carrier.team
            self.last_ball_x = ball_carrier.position.x
        else:
            self.last_ball_team = None
            self.last_ball_x = None
        return reward

    def _has_ball(self, game):
        ball_carrier = game.get_ball_carrier()
        return self.last_ball_team == self.my_team and ball_carrier.team == self.my_team

    def calculate_tackle_zones_reward(self, game):
        board_tackle_zones = self._get_initial_tackle_zones(game)
        ball = game.get_ball()
        if ball is not None:
            self._adjust_for_ball_location(board_tackle_zones, ball.position, game.arena.height, game.arena.width)
        reward = np.nansum(np.where(board_tackle_zones is None, np.nan, board_tackle_zones)) * self.TACKLE_ZONE_REWARD
        return self._positive_multiply(reward)

    def _get_initial_tackle_zones(self, game):
        board_tackle_zones = np.zeros((game.arena.height, game.arena.width))
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        for y, row in enumerate(game.state.pitch.board):
            for x, player in enumerate(row):
                if player:
                    board_tackle_zones[y][x] = None
                    for dy, dx in directions:
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < game.arena.height and 0 <= nx < game.arena.width:
                            if game.state.pitch.board[ny][nx] is None:
                                board_tackle_zones[ny][nx] += 1 if player.team == self.my_team else -1
                                if board_tackle_zones[ny][nx] == 2:
                                    board_tackle_zones[ny][nx] += self.DOUBLE_BLOCK_BONUS
                            else:
                                board_tackle_zones[ny][nx] = None
        return board_tackle_zones

    def _adjust_for_ball_location(self, board_tackle_zones, ball_position, arena_height, arena_width):
        ball_x, ball_y = ball_position.x, ball_position.y
        if board_tackle_zones[ball_y][ball_x] is not None:
            board_tackle_zones[ball_y][ball_x] *= self.TACKLE_ZONE_BALL_WEIGHT
        for dy in range(-self.TACKLE_ZONE_BALL_FAR_RANGE, self.TACKLE_ZONE_BALL_FAR_RANGE + 1):
            for dx in range(-self.TACKLE_ZONE_BALL_FAR_RANGE, self.TACKLE_ZONE_BALL_FAR_RANGE + 1):
                ny, nx = ball_y + dy, ball_x + dx
                if 0 <= ny < arena_height and 0 <= nx < arena_width:
                    distance = abs(dy) + abs(dx)
                    if distance == 1:
                        if board_tackle_zones[ny][nx] is not None:
                            board_tackle_zones[ny][nx] *= self.TACKLE_ZONE_BALL_CLOSE_RANGE_WEIGHT
                    elif 1 < distance <= self.TACKLE_ZONE_BALL_FAR_RANGE:
                        if board_tackle_zones[ny][nx] is not None:
                            board_tackle_zones[ny][nx] *= self.TACKLE_ZONE_BALL_FAR_RANGE_WEIGHT

    def calculate_control_ball_reward(self, game):
        ball_carrier = game.get_ball_carrier()
        if ball_carrier is not None:
            if (self._has_ball(game) and self.control_ball_reward < 0) or (not self._has_ball(game) and self.control_ball_reward > 0):
                self.control_ball_reward = 0
            self.control_ball_reward += self.CONTROL_BALL_REWARD if self._has_ball(game) else -self.CONTROL_BALL_REWARD
        else:
            self.control_ball_reward = 0
        return self._positive_multiply(self.control_ball_reward)

    def calculate_path_to_touchdown_reward(self, game):
        reward = 0.0
        ball_carrier = game.get_ball_carrier()
        if ball_carrier is not None:
            target = game.get_opp_endzone_x(self.my_team) if self._has_ball(game) else game.get_opp_endzone_x(self.opp_team)
            if ball_carrier.position.x is not target:
                paths = pathfinding_module.get_all_paths(game, ball_carrier)
                for path in paths:
                    distance = abs(target - path.steps[-1].x) if abs(target - path.steps[-1].x) > 0 else 1
                    if path.prob == 1 and game.num_tackle_zones_at(ball_carrier, path.get_last_step()) == 0:
                        reward += self.TOUCHDOWN_PATH_REWARD * self.TOUCHDOWN_CLEAR_PATH_WEIGHT
                    elif game.num_tackle_zones_at(ball_carrier, path.get_last_step()) == 0:
                        reward += self.TOUCHDOWN_PATH_REWARD * path.prob / distance
                    else:
                        reward += self.TOUCHDOWN_PATH_REWARD * path.prob / game.num_tackle_zones_at(ball_carrier, path.get_last_step()) * distance
        return (self._positive_multiply(reward) if self._has_ball(game) else -reward) / self.env_size

    def calculate_ball_pickup_reward(self, game):
        reward = 0.0
        if game.get_ball_carrier() is None:
            ball_position = game.get_ball_position()
            if ball_position is not None:
                for player in self.my_team.players:
                    if player.position is not None and player.position.distance(ball_position) <= player.get_ma():
                        reward += self._get_pickup_reward(game, ball_position, player,  self.my_team)
                for player in self.opp_team.players:
                    if player.position is not None and player.position.distance(ball_position) <= player.get_ma():
                        reward -= self._get_pickup_reward(game, ball_position, player,  self.opp_team)
        return self._positive_multiply(reward)

    def _get_pickup_reward(self, game, ball_position, player, team):
        if player.position.distance(ball_position) <= player.get_ma():
            path = pathfinding_module.get_safest_path(game, player, ball_position)
            if path is not None:
                distance_to_endzone = abs(game.get_opp_endzone_x(team) - path.steps[-1].x)
                if distance_to_endzone != 0:
                    return self.PICKUP_TO_ENDZONE_PATH_REWARD / distance_to_endzone
        return 0


def a2c_scripted_actions(game: Game):
    proc_type = type(game.get_procedure())
    if proc_type is procedure.Block:
        return CustomScriptedBot.block(self=None, game=game)
    return None
