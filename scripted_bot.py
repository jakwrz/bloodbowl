from typing import List

import botbowl
from botbowl import Action, ActionType, Square, BBDieResult, Skill, Formation, ProcBot
import botbowl.core.pathfinding as pathfinding_module
import time
import math
from botbowl.core.pathfinding.python_pathfinding import Path


class CustomScriptedBot(ProcBot):
    def __init__(self, name):
        super().__init__(name)
        self.my_team = None
        self.opp_team = None
        self.actions = []
        self.last_turn = 0
        self.last_half = 0
        self.open_players = None

        self.off_formation = [
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "m", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "x", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "S"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "x"],
            ["-", "-", "-", "-", "-", "s", "-", "-", "-", "0", "-", "-", "S"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "x"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "S"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "x", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "m", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"]
        ]

        self.def_formation = [
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "x", "-", "b", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "x", "-", "S", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "0"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "0"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "0"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "x", "-", "S", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "x", "-", "b", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"],
            ["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"]
        ]

        self.off_formation = Formation("Wedge offense", self.off_formation)
        self.def_formation = Formation("Zone defense", self.def_formation)
        self.setup_actions = []

    def new_game(self, game, team):
        self.my_team = team
        self.opp_team = game.get_opp_team(team)
        self.last_turn = 0
        self.last_half = 0

    def coin_toss_flip(self, game):
        return Action(ActionType.TAILS)

    def coin_toss_kick_receive(self, game):
        return Action(ActionType.RECEIVE)

    def setup(self, game):
        self.my_team = game.get_team_by_id(self.my_team.team_id)
        self.opp_team = game.get_opp_team(self.my_team)

        if self.setup_actions:
            action = self.setup_actions.pop(0)
            return action
        if game.arena.width == 28 and game.arena.height == 17:
            if game.get_receiving_team() == self.my_team:
                self.setup_actions = self.off_formation.actions(game, self.my_team)
                self.setup_actions.append(Action(ActionType.END_SETUP))
            else:
                self.setup_actions = self.def_formation.actions(game, self.my_team)
                self.setup_actions.append(Action(ActionType.END_SETUP))
            action = self.setup_actions.pop(0)
            return action

        for action_choice in game.get_available_actions():
            if action_choice.action_type != ActionType.END_SETUP and action_choice.action_type != ActionType.PLACE_PLAYER:
                self.setup_actions.append(Action(ActionType.END_SETUP))
                return Action(action_choice.action_type)

        return None

    def turn(self, game):
        self.turn_setup(game)
        actions = game.state.available_actions
        if len(actions) == 1 and \
                actions[0].action_type == ActionType.END_TURN:
            self.actions = [Action(ActionType.END_TURN)]
        while len(self.actions) > 0:
            action = self.get_next_action()
            if game._is_action_allowed(action):
                return action
        self.make_plan(game)
        action = self.get_next_action()
        return action

    def get_next_action(self):
        action = self.actions[0]
        self.actions = self.actions[1:]
        return action

    def make_plan(self, game):
        self.open_players = None
        if not self.try_actions(game):
            self.open_players = self.get_open_players(game)
            if not self.try_actions(game):
                self.actions.append(Action(ActionType.END_TURN))

    def try_actions(self, game):
        prioritized_actions = [
            self.perform_fallen_players_standup,
            self.perform_ball_carrier_moving,
            self.perform_safe_block,
            self.perform_ball_pickup,
            self.perform_receivers_moving,
            self.perform_blitz_action,
            self.perform_caging_action,
            self.perform_assisting_player_moving,
            self.perform_towards_ball_moving,
            self.perform_risky_blocks
        ]
        for action in prioritized_actions:
            selected = action(game)
            if selected:
                return True
        return False

    def turn_setup(self, game):
        self.my_team = game.get_team_by_id(self.my_team.team_id)
        self.opp_team = game.get_opp_team(self.my_team)
        turn = game.get_agent_team(self).state.turn
        half = game.state.half
        if half > self.last_half or turn > self.last_turn:
            self.actions.clear()
            self.last_turn = turn
            self.last_half = half
            self.actions = []

    def perform_fallen_players_standup(self, game):
        for player in self.my_team.players:
            if player.position is not None and not player.state.up and not player.state.stunned and not player.state.used:
                if game.num_tackle_zones_in(player) > 0:
                    self.actions.append(Action(ActionType.START_MOVE, player=player))
                    self.actions.append(Action(ActionType.STAND_UP))
                    return True

    def perform_ball_carrier_moving(self, game):
        ball_carrier = game.get_ball_carrier()
        if ball_carrier is not None and ball_carrier.team == self.my_team and not ball_carrier.state.used:
            td_path = pathfinding_module.get_safest_path_to_endzone(game, ball_carrier, allow_team_reroll=True)
            if td_path is not None and td_path.prob >= 0.7:
                self.actions.append(Action(ActionType.START_MOVE, player=ball_carrier))
                self.actions.extend(path_to_move_actions(game, ball_carrier, td_path))
                return True

                handoff_path = self.find_player_in_scoring_range(game)
                if handoff_path is not None and (handoff_p >= 0.7 or self.my_team.state.turn == 8):
                    self.actions.append(Action(ActionType.START_HANDOFF, player=ball_carrier))
                    self.actions.extend(path_to_move_actions(game, ball_carrier, handoff_path))
                    return True

            if game.num_tackle_zones_in(ball_carrier) == 0:
                paths = pathfinding_module.get_all_paths(game, ball_carrier)
                best_path = None
                best_distance = 100
                target_x = game.get_opp_endzone_x(self.my_team)
                for path in paths:
                    distance_to_endzone = abs(target_x - path.steps[-1].x)
                    if path.prob == 1 and (best_path is None or distance_to_endzone < best_distance) and \
                            game.num_tackle_zones_at(ball_carrier, path.get_last_step()) == 0:
                        best_path = path
                        best_distance = distance_to_endzone
                if best_path is not None:
                    self.actions.append(Action(ActionType.START_MOVE, player=ball_carrier))
                    self.actions.extend(path_to_move_actions(game, ball_carrier, best_path))
                    return True

    def get_path_to_player_in_scoring_range(self, game):
        handoff_p = None
        path = None
        if game.is_handoff_available():
            unused_teammates = []
            for player in self.my_team.players:
                if player.position is not None and player != game.get_ball_carrier() and not player.state.used and player.state.up:
                    unused_teammates.append(player)
        for player in unused_teammates:
            if game.get_distance_to_endzone(player) > player.num_moves_left():
                continue
            td_path = pathfinding_module.get_safest_path_to_endzone(game, player, allow_team_reroll=True)
            if td_path is None:
                continue
            path = pathfinding_module.get_safest_path(game, game.get_ball_carrier(), player.position, allow_team_reroll=True)
            if path is None:
                continue
            p_catch = game.get_catch_prob(player, handoff=True, allow_catch_reroll=True, allow_team_reroll=True)
            p = td_path.prob * path.prob * p_catch
            if handoff_p is None or p > handoff_p:
                handoff_player = p
                path = path
        return path

    def perform_safe_block(self, game):
        attacker, defender, p_self_up, p_opp_down, block_p_fumble_self, block_p_fumble_opp = self.get_safest_block(game)
        if attacker is not None and p_self_up > 0.94 and block_p_fumble_self == 0:
            self.actions.append(Action(ActionType.START_BLOCK, player=attacker))
            self.actions.append(Action(ActionType.BLOCK, position=defender.position))
            return True

    def perform_ball_pickup(self, game):
        if game.get_ball_carrier() is None:
            pickup_p = None
            pickup_player = None
            pickup_path = None
            for player in self.my_team.players:
                if player.position is not None and not player.state.used:
                    if player.position.distance(game.get_ball_position()) <= player.get_ma() + 2:
                        path = pathfinding_module.get_safest_path(game, player, game.get_ball_position())
                        if path is not None:
                            p = path.prob
                            if pickup_p is None or p > pickup_p:
                                pickup_p = p
                                pickup_player = player
                                pickup_path = path
            if pickup_player is not None and pickup_p > 0.33:
                self.actions.append(Action(ActionType.START_MOVE, player=pickup_player))
                self.actions.extend(path_to_move_actions(game, pickup_player, pickup_path))
                if game.num_tackle_zones_at(pickup_player, game.get_ball_position()) == 0 and game.get_opp_endzone_x(self.my_team) != game.get_ball_position().x:
                    best_path = self.get_safest_path_to_endzone(pickup_player, pickup_path)
                    if best_path is not None:
                        self.actions.extend(path_to_move_actions(game, pickup_player, best_path, do_assertions=False))
                return True

    def get_safest_path_to_endzone(self, game, pickup_player, pickup_path):
        best_path = None
        best_distance = 100
        paths = pathfinding_module.get_all_paths(game, pickup_player, from_position=game.get_ball_position(), num_moves_used=len(pickup_path))
        target_x = game.get_opp_endzone_x(self.my_team)
        for path in paths:
            distance_to_endzone = abs(target_x - path.steps[-1].x)
            if path.prob == 1 and (
                    best_path is None or distance_to_endzone < best_distance) and game.num_tackle_zones_at(
                    pickup_player, path.get_last_step()) == 0:
                best_path = path
                best_distance = distance_to_endzone
        return best_path

    def get_open_players(self, game):
        open_players = []
        for player in self.my_team.players:
            if player.position is not None and not player.state.used and game.num_tackle_zones_in(player) == 0:
                open_players.append(player)
        return open_players

    def perform_receivers_moving(self, game):
        for player in self.open_players:
            if player.has_skill(Skill.CATCH) and player != game.get_ball_carrier():
                if game.get_distance_to_endzone(player) > player.num_moves_left():
                    continue
                paths = pathfinding_module.get_all_paths(game, player)
                best_path = None
                best_distance = 100
                target_x = game.get_opp_endzone_x(self.my_team)
                for path in paths:
                    distance_to_endzone = abs(target_x - path.steps[-1].x)
                    if path.prob == 1 and (best_path is None or distance_to_endzone < best_distance) and game.num_tackle_zones_at(player, path.get_last_step()):
                        best_path = path
                        best_distance = distance_to_endzone
                if best_path is not None:
                    self.actions.append(Action(ActionType.START_MOVE, player=player))
                    self.actions.extend(path_to_move_actions(game, player, best_path))
                    return True

    def perform_blitz_action(self, game):
        if game.is_blitz_available():
            best_blitz_attacker = None
            best_blitz_score = None
            best_blitz_path = None
            for blitzer in self.open_players:
                if blitzer.position is not None and not blitzer.state.used and blitzer.has_skill(Skill.BLOCK):
                    blitz_paths = pathfinding_module.get_all_paths(game, blitzer, blitz=True)
                    for path in blitz_paths:
                        defender = game.get_player_at(path.get_last_step())
                        if defender is None:
                            continue
                        from_position = path.steps[-2] if len(path.steps)>1 else blitzer.position
                        p_self, p_opp, p_fumble_self, p_fumble_opp = game.get_blitz_probs(blitzer, from_position, defender)
                        p_self_up = path.prob * (1-p_self)
                        p_opp = path.prob * p_opp
                        p_fumble_opp = p_fumble_opp * path.prob
                        if blitzer == game.get_ball_carrier():
                            p_fumble_self = path.prob + (1 - path.prob) * p_fumble_self
                        score = p_self_up + p_opp + p_fumble_opp - p_fumble_self
                        if best_blitz_score is None or score > best_blitz_score:
                            best_blitz_attacker = blitzer
                            best_blitz_score = score
                            best_blitz_path = path
            if best_blitz_attacker is not None and best_blitz_score >= 1.25:
                self.actions.append(Action(ActionType.START_BLITZ, player=best_blitz_attacker))
                self.actions.extend(path_to_move_actions(game, best_blitz_attacker, best_blitz_path))
                return True

    def perform_caging_action(self, game):
        ball_pos = game.get_ball_position()
        cage = [
            Square(ball_pos.x - 1, ball_pos.y - 1),
            Square(ball_pos.x + 1, ball_pos.y - 1),
            Square(ball_pos.x - 1, ball_pos.y + 1),
            Square(ball_pos.x + 1, ball_pos.y + 1)
        ]
        if game.get_ball_carrier():
            for cage_position in cage:
                if self._is_valid_cage_position(game, cage_position):
                    for player in self.open_players:
                        if self._is_eligible_player(game, player, cage_position, cage):
                            path = pathfinding_module.get_safest_path(game, player, cage_position)
                            if self._is_safe_path(path):
                                self._move_player_to_cage(game, player, path)
                                return True

    def _is_valid_cage_position(self, game, cage_position):
        return game.get_player_at(cage_position) is None and not game.is_out_of_bounds(cage_position)

    def _is_eligible_player(self, game, player, cage_position, cage):
        return (player != game.get_ball_carrier() and
                player.position not in cage and
                player.position.distance(cage_position) <= player.num_moves_left() and
                game.num_tackle_zones_in(player) == 0)

    def _is_safe_path(self, path):
        return path is not None and path.prob > 0.90

    def _move_player_to_cage(self, game, player, path):
        self.actions.append(Action(ActionType.START_MOVE, player=player))
        self.actions.extend(path_to_move_actions(game, player, path))

    def perform_assisting_player_moving(self, game, open_players):
        for player in open_players:
            assist_positions = self._find_assist_positions(game)
            if self._try_assist_move(game, player, assist_positions):
                return True

    def _try_assist_move(self, game, player, assist_positions):
        for path in pathfinding_module.get_all_paths(game, player):
            if self._is_valid_assist_path(path, assist_positions):
                self._execute_assist_move(game, player, path)
                return True

    def _is_valid_assist_path(self, path, assist_positions):
        return path.prob >= 0.9 and path.get_last_step() in assist_positions

    def _execute_assist_move(self, game, player, path):
        self.actions.append(Action(ActionType.START_MOVE, player=player))
        self.actions.extend(path_to_move_actions(game, player, path))

    def _find_assist_positions(self, game):
        assist_positions = set()
        for player in game.get_opp_team(self.my_team).players:
            if self._is_valid_opponent_for_assist(player):
                self._add_assist_positions(game, player, assist_positions)
        return assist_positions

    def _is_valid_opponent_for_assist(self, player):
        return player.position is not None and player.state.up

    def _add_assist_positions(self, game, player, assist_positions):
        for opponent in game.get_adjacent_opponents(player, down=False):
            att_str, def_str = game.get_block_strengths(player, opponent)
            if def_str >= att_str:
                for open_position in game.get_adjacent_squares(player.position, occupied=False):
                    if len(game.get_adjacent_players(open_position, team=self.opp_team, down=False)) == 1:
                        assist_positions.add(open_position)

    def perform_towards_ball_moving(self, game):
        for player in self.open_players:
            if player == game.get_ball_carrier() or game.num_tackle_zones_in(player) > 0:
                continue
            shortest_distance = None
            path = None
            if game.get_ball_carrier() is None:
                for p in pathfinding_module.get_all_paths(game, player):
                    distance = p.get_last_step().distance(game.get_ball_position())
                    if shortest_distance is None or (p.prob == 1 and distance < shortest_distance):
                        shortest_distance = distance
                        path = p
            elif game.get_ball_carrier().team != self.my_team:
                for p in pathfinding_module.get_all_paths(game, player):
                    distance = p.get_last_step().distance(game.get_ball_carrier().position)
                    if shortest_distance is None or (p.prob == 1 and distance < shortest_distance):
                        shortest_distance = distance
                        path = p
            if path is not None:
                self.actions.append(Action(ActionType.START_MOVE, player=player))
                self.actions.extend(path_to_move_actions(game, player, path))
                return True

    def perform_risky_blocks(self, game):
        attacker, defender, p_self_up, p_opp_down, block_p_fumble_self, block_p_fumble_opp = self.get_safest_block(game)
        if attacker is not None and (p_opp_down > (1-p_self_up) or block_p_fumble_opp > 0):
            self.actions.append(Action(ActionType.START_BLOCK, player=attacker))
            self.actions.append(Action(ActionType.BLOCK, position=defender.position))
            return True

    def get_safest_block(self, game):
        block_attacker = None
        block_defender = None
        block_p_self_up = None
        block_p_opp_down = None
        block_p_fumble_self = None
        block_p_fumble_opp = None
        for attacker in self.my_team.players:
            if attacker.position is not None and not attacker.state.used and attacker.state.up:
                for defender in game.get_adjacent_opponents(attacker, down=False):
                    p_self, p_opp, p_fumble_self, p_fumble_opp = game.get_block_probs(attacker, defender)
                    p_self_up = (1-p_self)
                    if block_p_self_up is None or (p_self_up > block_p_self_up and p_opp >= p_fumble_self):
                        block_p_self_up = p_self_up
                        block_p_opp_down = p_opp
                        block_attacker = attacker
                        block_defender = defender
                        block_p_fumble_self = p_fumble_self
                        block_p_fumble_opp = p_fumble_opp
        return block_attacker, block_defender, block_p_self_up, block_p_opp_down, block_p_fumble_self, block_p_fumble_opp

    def player_action(self, game):
        while len(self.actions) > 0:
            action = self.get_next_action()
            if game._is_action_allowed(action):
                return action

        ball_carrier = game.get_ball_carrier()
        if ball_carrier == game.get_active_player():
            td_path = pathfinding_module.get_safest_path_to_endzone(game, ball_carrier)
            if td_path is not None and td_path.prob <= 0.9:
                self.actions.extend(path_to_move_actions(game, ball_carrier, td_path))
                return self.get_next_action()
        return Action(ActionType.END_PLAYER_TURN)

    def perfect_defense(self, game):
        return Action(ActionType.END_SETUP)

    def reroll(self, game):
        reroll_proc = game.get_procedure()
        context = reroll_proc.context
        if type(context) == botbowl.Dodge:
            return Action(ActionType.USE_REROLL)
        if type(context) == botbowl.Pickup:
            return Action(ActionType.USE_REROLL)
        if type(context) == botbowl.PassAttempt:
            return Action(ActionType.USE_REROLL)
        if type(context) == botbowl.Catch:
            return Action(ActionType.USE_REROLL)
        if type(context) == botbowl.GFI:
            return Action(ActionType.USE_REROLL)
        if type(context) == botbowl.BloodLust:
            return Action(ActionType.USE_REROLL)
        if type(context) == botbowl.Block:
            attacker = context.attacker
            attackers_down = 0
            for die in context.roll.dice:
                if die.get_value() == BBDieResult.ATTACKER_DOWN:
                    attackers_down += 1
                elif die.get_value() == BBDieResult.BOTH_DOWN and not attacker.has_skill(Skill.BLOCK) and not attacker.has_skill(Skill.WRESTLE):
                    attackers_down += 1
            if attackers_down > 0 and context.favor != self.my_team:
                return Action(ActionType.USE_REROLL)
            if attackers_down == len(context.roll.dice) and context.favor != self.opp_team:
                return Action(ActionType.USE_REROLL)
            return Action(ActionType.DONT_USE_REROLL)
        return Action(ActionType.DONT_USE_REROLL)

    def place_ball(self, game):
        side_width = game.arena.width / 2
        side_height = game.arena.height
        squares_from_left = math.ceil(side_width / 2)
        squares_from_right = math.ceil(side_width / 2)
        squares_from_top = math.floor(side_height / 2)
        left_center = Square(squares_from_left, squares_from_top)
        right_center = Square(game.arena.width - 1 - squares_from_right, squares_from_top)
        if game.is_team_side(left_center, self.opp_team):
            return Action(ActionType.PLACE_BALL, position=left_center)
        return Action(ActionType.PLACE_BALL, position=right_center)

    def high_kick(self, game):
        ball_pos = game.get_ball_position()
        if game.is_team_side(game.get_ball_position(), self.my_team) and \
                game.get_player_at(game.get_ball_position()) is None:
            for player in game.get_players_on_pitch(self.my_team, up=True):
                if Skill.BLOCK in player.get_skills() and game.num_tackle_zones_in(player) == 0:
                    return Action(ActionType.SELECT_PLAYER, player=player, position=ball_pos)
        return Action(ActionType.SELECT_NONE)

    def touchback(self, game):
        p = None
        for player in game.get_players_on_pitch(self.my_team, up=True):
            if Skill.BLOCK in player.get_skills():
                return Action(ActionType.SELECT_PLAYER, player=player)
            p = player
        return Action(ActionType.SELECT_PLAYER, player=p)

    def blitz(self, game):
        return Action(ActionType.END_TURN)

    def use_bribe(self, game):
        return Action(ActionType.USE_BRIBE)

    def block(self, game):
        attacker = game.get_procedure().attacker
        defender = game.get_procedure().defender
        is_blitz = game.get_procedure().blitz
        dice = game.num_block_dice(attacker, defender, blitz = is_blitz)
        actions = {action_choice.action_type for action_choice in game.state.available_actions}

        if ActionType.SELECT_DEFENDER_DOWN in actions:
            return Action(ActionType.SELECT_DEFENDER_DOWN)
        if ActionType.SELECT_DEFENDER_STUMBLES in actions and not (
                defender.has_skill(Skill.DODGE) and not attacker.has_skill(Skill.TACKLE)):
            return Action(ActionType.SELECT_DEFENDER_STUMBLES)
        if ActionType.SELECT_BOTH_DOWN in actions and not defender.has_skill(Skill.BLOCK) and (
                attacker.has_skill(Skill.BLOCK) or game.get_ball_carrier() == defender):
            return Action(ActionType.SELECT_BOTH_DOWN)
        if ActionType.USE_REROLL in actions and game.get_ball_carrier() == defender:
            return Action(ActionType.USE_REROLL)
        if ActionType.SELECT_PUSH in actions:
            return Action(ActionType.SELECT_PUSH)
        if ActionType.USE_REROLL in actions and dice > 1:
            return Action(ActionType.USE_REROLL)
        if ActionType.SELECT_ATTACKER_DOWN in actions:
            return Action(ActionType.SELECT_ATTACKER_DOWN)
        return Action(ActionType.END_TURN)

    def push(self, game):
        for position in game.state.available_actions[0].positions:
            return Action(ActionType.PUSH, position=position)

    def follow_up(self, game):
        player = game.state.active_player
        for position in game.state.available_actions[0].positions:
            if player.position != position:
                return Action(ActionType.FOLLOW_UP, position=position)

    def apothecary(self, game):
        return Action(ActionType.USE_APOTHECARY)

    def interception(self, game):
        for action in game.state.available_actions:
            if action.action_type == ActionType.SELECT_PLAYER:
                for player, rolls in zip(action.players, action.rolls):
                    return Action(ActionType.SELECT_PLAYER, player=player)
        return Action(ActionType.SELECT_NONE)

    def quick_snap(self, game):
        return Action(ActionType.END_TURN)

    def blitz(self, game):
        return Action(ActionType.END_TURN)

    def pass_action(self, game):
        return Action(ActionType.USE_REROLL)

    def catch(self, game):
        return Action(ActionType.USE_REROLL)

    def gfi(self, game):
        return Action(ActionType.USE_REROLL)

    def dodge(self, game):
        return Action(ActionType.USE_REROLL)

    def pickup(self, game):
        return Action(ActionType.USE_REROLL)

    def use_juggernaut(self, game):
        return Action(ActionType.USE_SKILL)

    def use_wrestle(self, game):
        return Action(ActionType.USE_SKILL)

    def use_stand_firm(self, game):
        return Action(ActionType.USE_SKILL)

    def use_pro(self, game):
        return Action(ActionType.USE_SKILL)

    def use_bribe(self, game):
        return Action(ActionType.USE_BRIBE)

    def blood_lust_block_or_move(self, game):
        return Action(ActionType.START_BLOCK)

    def eat_thrall(self, game):
        position = game.get_available_actions()[0].positions[0]
        return Action(ActionType.SELECT_PLAYER, position)

    def end_game(self, game):
        winner = game.get_winning_team()


def path_to_move_actions(game: botbowl.Game, player: botbowl.Player, path: Path, do_assertions=True) -> List[Action]:
    if path.block_dice is not None:
        action_type = ActionType.BLOCK
    elif path.handoff_roll is not None:
        action_type = ActionType.HANDOFF
    elif path.foul_roll is not None:
        action_type = ActionType.FOUL
    else:
        action_type = ActionType.MOVE

    active_team = game.state.available_actions[0].team
    player_at_target = game.get_player_at(path.get_last_step())

    if do_assertions:
        if action_type is ActionType.MOVE:
            assert player_at_target is None or player_at_target is game.get_active_player()
        elif action_type is ActionType.BLOCK:
            assert game.get_opp_team(active_team) is player_at_target.team
            assert player_at_target.state.up
        elif action_type is ActionType.FOUL:
            assert game.get_opp_team(active_team) is player_at_target.team
            assert not player_at_target.state.up
        elif action_type is ActionType.HANDOFF:
            assert active_team is player_at_target.team
            assert player_at_target.state.up
        else:
            raise Exception(f"Unregonized action type {action_type}")

    final_action = Action(action_type, position=path.get_last_step())

    if game._is_action_allowed(final_action):
        return [final_action]
    else:
        actions = []
        if not player.state.up and path.steps[0] == player.position:
            actions.append(Action(ActionType.STAND_UP, player=player))
            actions.extend(Action(ActionType.MOVE, position=sq) for sq in path.steps[1:-1])
        else:
            actions.extend(Action(ActionType.MOVE, position=sq) for sq in path.steps[:-1])
        actions.append(final_action)
        return actions

botbowl.register_bot('scripted-2', CustomScriptedBot)


def main():
    config = botbowl.load_config("bot-bowl")
    config.competition_mode = False
    config.pathfinding_enabled = True
    ruleset = botbowl.load_rule_set(config.ruleset, all_rules=False)
    arena = botbowl.load_arena(config.arena)
    home = botbowl.load_team_by_filename("human", ruleset)
    away = botbowl.load_team_by_filename("human", ruleset)

    num_games = 10
    wins = 0
    tds = 0
    for i in range(num_games):
        home_agent = botbowl.make_bot('scripted-2')
        home_agent.name = "Scripted Bot"
        away_agent = botbowl.make_bot('random')
        away_agent.name = "Random Bot"
        config.debug_mode = False
        game = botbowl.Game(i, home, away, home_agent, away_agent, config, arena=arena, ruleset=ruleset)
        game.config.fast_mode = True

        print("Starting game", (i+1))
        start = time.time()
        game.init()
        end = time.time()
        print(end - start)

        wins += 1 if game.get_winning_team() is game.state.home_team else 0
        tds += game.state.home_team.state.score


if __name__ == "__main__":
    main()