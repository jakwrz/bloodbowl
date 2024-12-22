import botbowl
from botbowl import EnvConf
from implementation.a2c.a2c_agent import A2CAgent
from implementation.a2c.a2c_env import a2c_scripted_actions

model_name = 'long'
model_name_opponent = 'balance'
env_name = f'botbowl-11'
model_filename = f"models/{env_name}/{model_name}.nn"
model_filename_opponent = f"models/{env_name}/{model_name_opponent}.nn"
log_filename = f"logs/{env_name}/{env_name}.dat"
num_games = 100000


def main():
    def _make_my_a2c_bot(name, env_size=11):
        return A2CAgent(name=name,
                        env_conf=EnvConf(size=env_size),
                        scripted_func=a2c_scripted_actions,
                        filename=model_filename)
    botbowl.register_bot('bot', _make_my_a2c_bot)

    def _make_my_a2c_bot_opponent(name, env_size=11):
        return A2CAgent(name=name,
                        env_conf=EnvConf(size=env_size),
                        scripted_func=a2c_scripted_actions,
                        filename=model_filename_opponent)
    botbowl.register_bot('bot-opponent', _make_my_a2c_bot_opponent)


    config = botbowl.load_config("bot-bowl")
    config.competition_mode = False
    config.pathfinding_enabled = False
    ruleset = botbowl.load_rule_set(config.ruleset)
    arena = botbowl.load_arena(config.arena)
    home = botbowl.load_team_by_filename("human", ruleset)
    away = botbowl.load_team_by_filename("human", ruleset)
    config.competition_mode = False
    config.debug_mode = False

    wins = 0
    draws = 0
    n = num_games
    is_home = True
    tds_away = 0
    tds_home = 0
    for i in range(n):

        if is_home:
            away_agent = botbowl.make_bot('bot-opponent')
            home_agent = botbowl.make_bot('bot')
        else:
            away_agent = botbowl.make_bot('bot')
            home_agent = botbowl.make_bot("bot-opponent")
        game = botbowl.Game(i, home, away, home_agent, away_agent, config, arena=arena, ruleset=ruleset)
        game.config.fast_mode = True

        game.init()

        winner = game.get_winner()
        if winner is None:
            draws += 1
        elif winner == home_agent and is_home:
            wins += 1
        elif winner == away_agent and not is_home:
            wins += 1

        tds_home += game.get_agent_team(home_agent).state.score
        tds_away += game.get_agent_team(away_agent).state.score

    print(f"Home/Draws/Away: {wins}/{draws}/{n-wins-draws}")
    print(f"Home TDs per game: {tds_home/n}")
    print(f"Away TDs per game: {tds_away/n}")

if __name__ == "__main__":
    main()