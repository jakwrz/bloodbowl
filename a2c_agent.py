from typing import Callable

import torch
import torch.nn as nn
import torch.nn.functional as F


import botbowl
from botbowl.ai.env import EnvConf, BotBowlEnv
from implementation.a2c.a2c_env import a2c_scripted_actions
from botbowl.ai.layers import *

model_name = 'long'
model_name_opponent = 'balance'
env_name = f'botbowl-11'
model_filename = f"models/{env_name}/{model_name}.nn"
model_filename_opponent = f"models/{env_name}/{model_name_opponent}.nn"
log_filename = f"logs/{env_name}/{env_name}.dat"
num_games = 1000


class CNNPolicy(nn.Module):
    def __init__(self, spatial_shape, non_spatial_inputs, hidden_nodes, kernels, actions):
        super(CNNPolicy, self).__init__()
        self.conv1 = nn.Conv2d(spatial_shape[0], out_channels=kernels[0], kernel_size=3, stride=1, padding=1)
        self.conv2 = nn.Conv2d(in_channels=kernels[0], out_channels=kernels[1], kernel_size=3, stride=1, padding=1)
        self.linear0 = nn.Linear(non_spatial_inputs, hidden_nodes)
        stream_size = kernels[1] * spatial_shape[1] * spatial_shape[2]
        stream_size += hidden_nodes
        self.linear1 = nn.Linear(stream_size, hidden_nodes)
        self.critic = nn.Linear(hidden_nodes, 1)
        self.actor = nn.Linear(hidden_nodes, actions)

        self.train()
        self.reset_parameters()

    def reset_parameters(self):
        relu_gain = nn.init.calculate_gain('relu')
        self.conv1.weight.data.mul_(relu_gain)
        self.conv2.weight.data.mul_(relu_gain)
        self.linear0.weight.data.mul_(relu_gain)
        self.linear1.weight.data.mul_(relu_gain)
        self.actor.weight.data.mul_(relu_gain)
        self.critic.weight.data.mul_(relu_gain)

    def forward(self, spatial_input, non_spatial_input):
        x1 = self.conv1(spatial_input.cuda())
        x1 = F.relu(x1)
        x1 = self.conv2(x1)
        x1 = F.relu(x1)
        flatten_x1 = x1.flatten(start_dim=1)
        x2 = self.linear0(non_spatial_input.cuda())
        x2 = F.relu(x2)
        flatten_x2 = x2.flatten(start_dim=1)
        concatenated = torch.cat((flatten_x1, flatten_x2), dim=1)
        x3 = self.linear1(concatenated)
        x3 = F.relu(x3)
        value = self.critic(x3)
        actor = self.actor(x3)
        return value, actor

    def act(self, spatial_inputs, non_spatial_input, action_mask):
        values, action_probs = self.get_action_probs(spatial_inputs, non_spatial_input, action_mask=action_mask)
        actions = action_probs.multinomial(1)
        for i, action in enumerate(actions):
            i = torch.tensor(i, dtype=torch.long, device=action.device)
            correct_action = action
            while not action_mask[i][action]:
                correct_action = action_probs[i].multinomial(1)
            actions[i] = correct_action
        return values, actions

    def evaluate_actions(self, spatial_inputs, non_spatial_input, actions, actions_mask):
        value, policy = self(spatial_inputs, non_spatial_input)
        actions_mask = actions_mask.view(-1, 1, actions_mask.shape[2]).squeeze().bool()
        policy[~actions_mask] = float('-inf')
        log_probs = F.log_softmax(policy, dim=1)
        probs = F.softmax(policy, dim=1)
        action_log_probs = log_probs.gather(1, actions)
        log_probs = torch.where(log_probs[None, :] == float('-inf'), torch.tensor(0.), log_probs)
        dist_entropy = -(log_probs * probs).sum(-1).mean()
        return action_log_probs, value, dist_entropy

    def get_action_probs(self, spatial_input, non_spatial_input, action_mask):
        values, actions = self(spatial_input, non_spatial_input)
        if action_mask is not None:
            actions[~action_mask] = float('-inf')
        action_probs = F.softmax(actions, dim=1)
        return values, action_probs


class A2CAgent(Agent):
    env: BotBowlEnv

    def __init__(self, name,
                 env_conf: EnvConf,
                 scripted_func: Callable[[Game], Optional[Action]] = None,
                 filename=model_filename):
        super().__init__(name)
        self.env = BotBowlEnv(env_conf)

        self.scripted_func = scripted_func
        self.action_queue = []

        # MODEL
        self.policy = torch.load(filename)
        self.policy.eval()
        self.end_setup = False

    def new_game(self, game, team):
        pass

    @staticmethod
    def _update_obs(array: np.ndarray):
        return torch.unsqueeze(torch.from_numpy(array.copy()), dim=0)

    def act(self, game):
        if len(self.action_queue) > 0:
            return self.action_queue.pop(0)

        if self.scripted_func is not None:
            scripted_action = self.scripted_func(game)
            if scripted_action is not None:
                return scripted_action

        self.env.game = game

        spatial_obs, non_spatial_obs, action_mask = map(A2CAgent._update_obs, self.env.get_state())
        non_spatial_obs = torch.unsqueeze(non_spatial_obs, dim=0)

        _, actions = self.policy.act(
            spatial_obs.float().cuda(),
            non_spatial_obs.float().cuda(),
            action_mask.cuda()
        )

        action_idx = actions[0].item()
        action_objects = self.env._compute_action(action_idx)

        self.action_queue = action_objects
        return self.action_queue.pop(0)

    def end_game(self, game):
        pass