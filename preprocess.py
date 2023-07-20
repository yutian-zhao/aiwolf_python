import os
import torch
import copy
import random
import torch.nn.functional as F
import numpy as np
import random

def count_log(dir):
    log_count = 0 
    for root, dirs, files in os.walk(dir, topdown=True):
        dirs.sort()
        if len(dirs)==0:
            for name in sorted(files):
                if name.endswith(".log"):
                    log_count += 1
    return log_count

MAX_DAY_LENGTH = 14
NAME = "debug_data" # 'debug_data' # 'temp_dataset' # gat2017log15
dir = f"data/{NAME}" # broken file: 398/076, 023/017
NUM_LOGS = count_log(dir) # 10000 # 10000 # 99998 # 10^5-2
ROLES = ["VILLAGER", "SEER", "MEDIUM", "BODYGUARD", "WEREWOLF", "POSSESSED"]
HUMAN_ROLES = ["VILLAGER", "SEER", "MEDIUM", "BODYGUARD"]
ROLES_DICT = {"VILLAGER":1, "SEER":2, "MEDIUM":3, "BODYGUARD":4, "WEREWOLF":5, "POSSESSED":6}
TOKEN_TYPES = ['status', 'divine', 'whisper', 'guard', 'attackVote',    'attack', 'talk', 'vote', 'execute', 'result']
num_player = 15
num_channel = 8
data = torch.empty(NUM_LOGS, MAX_DAY_LENGTH, num_channel, num_player, num_player)
labels = torch.empty(NUM_LOGS, num_player)
vote_labels = torch.empty(NUM_LOGS, MAX_DAY_LENGTH, num_player)
log_count = 0
talks = []

def get_content_list(content):
    content_list = []
    begin_idx = None
    lb = 0
    for idx, s in enumerate(content):
        if s == '(':
            lb += 1
            if begin_idx is None:
                begin_idx = idx
        if s == ')':
            lb -= 1
            if begin_idx and lb==0:
                content_list.append(content[begin_idx+1:idx])
                begin_idx = None
    return content_list



def parse_content(content, day_status, italker, update, day):
    '''
    italker
    parse content
        if simple:
    '''
    # for talk: 0 day; 1 type; 2 day id; 3 turn id; 4 subject; 5 content
    
    target_attitude = []

    if content.startswith('ESTIMATE'):
        itarget = int(content.split(" ")[1][-3:-1])-1
        estimate_role = content.split(" ")[-1]
        if estimate_role != 'ANY':
            estimate_result = ROLES_DICT[estimate_role]
            attitude = 1 if estimate_role in HUMAN_ROLES else -1 
            target_attitude.append((itarget, attitude))
            if update:
                day_status[0, 5, italker, itarget] = estimate_result
                day_status[0, 6, italker, itarget] = attitude
    elif content.startswith('COMINGOUT'):
        target_role = content.split(" ")[-1]
        if target_role != 'ANY':
            co_result = ROLES_DICT[target_role]
            if update:
                day_status[0, 4, italker] = co_result
            target_attitude.append((italker, 1))
    elif content.startswith('DIVINATION'):
        if update:
            day_status[0, 4, italker] = ROLES_DICT['SEER']
        target = content.split(" ")[1]
        if  target != 'ANY':
            itarget = int(target[-3:-1])-1
            if update:
                day_status[0, 6, italker, itarget] = -1
            target_attitude.append((itarget, -1))
    elif content.startswith('DIVINED'):
        if update:
            day_status[0, 4, italker] = ROLES_DICT['SEER']
        itarget = int(content.split(" ")[1][-3:-1])-1
        divined_result = 1 if content.split(" ")[-1] == 'HUMAN' else -1
        if update:
            day_status[0, 7, italker, itarget] = divined_result
        target_attitude.append((itarget, divined_result))
    elif content.startswith('IDENTIFIED'):
        if update:
            day_status[0, 4, italker] = ROLES_DICT['MEDIUM']
        itarget = int(content.split(" ")[1][-3:-1])-1
        identified_result = 1 if content.split(" ")[-1] == 'HUMAN' else -1
        if update:
            day_status[0, 7, italker, itarget] = identified_result
        target_attitude.append((itarget, identified_result))
    elif content.startswith('GUARD') or content.startswith('GUARDED'):
        if update:
            day_status[0, 4, italker] = ROLES_DICT['SEER']
        target = content.split(" ")[1]
        if  target != 'ANY':
            itarget = int(target[-3:-1])-1
            if update:
                day_status[0, 6, italker, itarget] = 1
            target_attitude.append((itarget, 1))
    elif content.startswith('VOTE'):
        target = content.split(" ")[1]
        if  target != 'ANY':
            itarget = int(content[-3:-1]) - 1
            if update:
                day_status[0, 6, italker, itarget] = -1
            target_attitude.append((itarget, -1))
    elif content.startswith('AGREE'):
        # day = tokens[0]
        content_tokens = content.split(" ")
        if content_tokens[1]=='TALK' and content_tokens[2]=='day'+day:
            talk_id = int(content_tokens[-1][3:])
            agree_content_tokens = talks[talk_id]
            _, ta_list = parse_content(agree_content_tokens[5], day_status, int(agree_content_tokens[4])-1, False, day)
            for t, a in ta_list:
                target_attitude.append((t, a))
                if update:
                    day_status[0, 6, italker, t] = a
    elif content.startswith('DISAGREE'):
        day = tokens[0]
        content_tokens = content.split(" ")
        if content_tokens[1]=='TALK' and content_tokens[2]=='day'+day:
            talk_id = int(content_tokens[-1][3:])
            agree_content_tokens = talks[talk_id]
            _, ta_list = parse_content(agree_content_tokens[5], day_status, int(agree_content_tokens[4])-1, False, day)
            for t, a in ta_list:
                target_attitude.append((t, -a))
                if update:
                    day_status[0, 6, italker, t] = -a
    elif content.startswith('NOT'):
        content_list = get_content_list(content)
        for c in content_list:
            _, ta_list = parse_content(c, day_status, italker, False, day)
            for t, a in ta_list:
                target_attitude.append((t, -a))
                if update:
                    day_status[0, 6, italker, t] = a
    elif content.startswith('AND') or content.startswith('OR') or content.startswith('XOR') or content.startswith('DAY'):
        content_list = get_content_list(content)
        for c in content_list:
            _, ta_list = parse_content(c, day_status, italker, True, day)
            for t, a in ta_list:
                target_attitude.append((t, a))
                if update:
                    day_status[0, 6, italker, t] = a
    elif content.startswith('REQUEST'):
        content_list = get_content_list(content)
        for c in content_list:
            _, ta_list = parse_content(c, day_status, italker, False, day)
            for t, a in ta_list:
                target_attitude.append((t, a))
                if update:
                    day_status[0, 6, italker, t] = a
    elif content.startswith('BECAUSE'):
        content_list = get_content_list(content)
        _, ta_list = parse_content(content_list[-1], day_status, italker, True, day)
        for t, a in ta_list:
            target_attitude.append((t, a))
            if update:
                day_status[0, 6, italker, t] = a
    
    return day_status, target_attitude

if __name__ == '__main__':
    for root, dirs, files in os.walk(dir, topdown=True):
        dirs.sort()
        if len(dirs)==0:
            for name in sorted(files):
                if name.endswith(".log"):
                    with open(os.path.join(root, name), "r") as f:
                        log_count += 1
                        lines = f.readlines()
                        day_checker = 1
                        game_end = False
                        id = None
                        id_role = {}
                        have_voted = []
                        vote_label_game = torch.empty((0, num_player))
                        vote_label_day = torch.zeros((1, num_player))
                        # role depend
                        role = "SEER" # random.choice(ROLES)
                        game_status = torch.empty((0, num_channel, num_player, num_player))
                        day_status = torch.zeros((1, num_channel, num_player, num_player))
                        prev_day_vote_matrix = torch.zeros((num_player, num_player))
                        vote_matrix = torch.zeros((num_player, num_player))
                        prev_executed = None # (id, -1/1)
                        medium_dead = False if role == "MEDIUM" else True
                        role_ids = set()
                        talks = []
                        divine_results = []
                        for line in lines:
                            line = line.strip()
                            tokens = line.split(",")
                            # for talk: 0 day; 1 type; 2 day id; 3 turn id; 4 subject; 5 content
                            # check validity
                            if int(tokens[0]) == 1 + day_checker:
                                ## init
                                # print("Day {} done.".format(day_checker))
                                if id:
                                    if role == 'WEREWOLF':
                                        for i in role_ids:
                                            day_status[0, 0, i] = ROLES_DICT[role]
                                    else:
                                        day_status[0, 0, id] = ROLES_DICT[role]
                                else:
                                    for i, r in id_role.items():
                                        if r == role:
                                            role_ids.add(i)
                                    id = random.choice(list(role_ids))
                                    # id = 2
                                    if role == 'WEREWOLF':
                                        for i in role_ids:
                                            day_status[0, 0, i] = ROLES_DICT[role]
                                    else:
                                        day_status[0, 0, id] = ROLES_DICT[role]
                                    
                                have_voted = []
                                talks = []
                                day_status[0, 2] = copy.deepcopy(prev_day_vote_matrix)
                                prev_day_vote_matrix = copy.deepcopy(vote_matrix)
                                vote_matrix = torch.zeros((num_player, num_player))
                                game_status = torch.cat((game_status, day_status), dim=0)
                                vote_label_game = torch.cat((vote_label_game, vote_label_day), dim=0)
                                day_checker += 1
                                day_status = torch.zeros((1, num_channel,  num_player, num_player))
                                vote_label_day = torch.zeros((1, num_player))
                                if prev_executed and not medium_dead:
                                    day_status[0, 3, prev_executed[0]] = prev_executed[1]
                                if len(divine_results)>0:
                                    divine_result = divine_results.pop(0)
                                    day_status[0, 3, divine_result[0]] = divine_result[1]
                            # elif int(tokens[0]) != day_checker:
                            #     raise Exception("Day check failed! Should be day {} or {}, but got {}.".format(day_checker, day_checker+1, tokens[0]))
                            assert tokens[1] in TOKEN_TYPES
                            assert not game_end

                            if tokens[1] == 'result':
                                game_end = True

                            if role == "SEER" and tokens[1]=='divine':
                                divine_results.append((int(tokens[3])-1, 1 if tokens[4]=='HUMAN' else -1))

                            # skip day 0
                            elif int(tokens[0]) == 0:
                                continue

                            # parse Alive status
                            elif tokens[1] == 'status':
                                if day_checker == 1:
                                    id_role[int(tokens[2])-1] = tokens[3]
                                if not medium_dead and 'MEDIUM,DEAD' in line:
                                    medium_dead = True
                                if tokens[4] == 'ALIVE':
                                    day_status[0, 1, [int(tokens[2])-1]] = 1 # broadcasting

                            elif tokens[1] == 'execute':
                                vote_label_day[0, int(tokens[2])-1] = 1
                                if not medium_dead:
                                    prev_executed = (int(tokens[2])-1, 1 if tokens[3] in HUMAN_ROLES else -1)
                                else:
                                    prev_executed = None
                            
                            elif tokens[1] == 'vote':
                                if not int(tokens[2]) in have_voted:
                                    have_voted.append(int(tokens[2]))
                                    vote_matrix[int(tokens[2])-1, int(tokens[3])-1] = 1
                            
                            elif tokens[1] == 'talk':
                                talks.append(tokens)
                                italker = int(tokens[4])-1
                                content = tokens[5]
                                day = tokens[0]
                                day_status, _ = parse_content(content, day_status, italker, True, day)

                        assert game_status.shape[0] <= MAX_DAY_LENGTH
                        # game_status = torch.unsqueeze(F.pad(game_status, (0, 0, 0, 0, 0, 0, 0, MAX_DAY_LENGTH-game_status.shape[0]), "constant", 0), 0)

                        for i in range(MAX_DAY_LENGTH-game_status.shape[0]):
                            game_status = torch.cat((game_status, torch.zeros((1, num_channel, num_player, num_player))), dim=0)
                        # game_status = torch.unsqueeze(game_status, 0)
                        # data = torch.cat((data, game_status), dim=0)
                        data[log_count-1] = game_status

                        vote_label_day = vote_label_game[[-1]]
                        for i in range(MAX_DAY_LENGTH-vote_label_game.shape[0]):
                            vote_label_game = torch.cat((vote_label_game, vote_label_day), dim=0)
                        vote_labels[log_count-1] = vote_label_game

                        label = []
                        for i in range(num_player):
                            label.append(ROLES_DICT[id_role[i]])
                        label = torch.tensor(label, dtype=torch.int) # unsqueeze
                        # labels = torch.cat((labels, label), dim=0)
                        labels[log_count-1] = label
                    
            print("{} done.".format(root))

    # assert log_count == NUM_LOGS, log_count # 10000 # 99998
    print("log_count: ", log_count)
    print("{} games loaded.".format(len(data)))
    # print(data[0][0])
    # print(len(data[0][0]))
    # print(vote_labels.shape)
    torch.save((data, labels, vote_labels), f"data/{NAME}.pt")
    with open("debug.log", 'w') as f, np.printoptions(threshold=np.inf):
        f.write(str(np.array(data)))
        f.write(str(np.array(labels)))