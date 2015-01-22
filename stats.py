import numpy as np
import db
import crawler

# input is a list of (commit, pullreq, evol)
def merge_evolution(list):
    evol_list = []
    for t in list:
        evol_list.append(len(t[2]))
    print_stats(evol_list)

#input is a map of <fork repo, list of branches where the pull request commits are made>
def branches(map):
    list = []
    for k,v in map.items():
        list.append(len(set(v)))
    print_stats(list)

def print_stats(list):
    print('max: ' + str(max(list)))
    print('min: ' + str(min(list)))
    print('mean: ' + str(np.mean(list)))
    print('std: ' + str(np.std(list)))

def get_unique_evol():
    unique_commits = {}
    all_evol_commits = 0
    #evolutionary commits that are both in the fork and upstream
    common_evol_commits = 0
    all_upstream_commits = crawler.get_all_commits_in_upstream('junit-team','junit')
    forks = db.get_fork_author()
    for fork in forks:
        evol_commits = db.get_fork_evol_commits(fork)
        all_evol_commits += len(evol_commits)

        #pullreq_commits = db.get_fork_pullreq_commits(fork)
        for ec in evol_commits:
            is_common = False
            for uc in all_upstream_commits:
                if uc.startswith(ec):
                    common_evol_commits += 1
                    is_common = True
                    break
            if not is_common:
                if fork in unique_commits:
                    unique_commits[fork].append(ec)
                else:
                    unique_commits[fork] = [ec]
    unique_ratio = ((all_evol_commits - common_evol_commits) / all_evol_commits) * 100
    print('unique evolution commits ratio: ' + "%.2f" % unique_ratio + ' (' + str(all_evol_commits - common_evol_commits) + '/' + str(all_evol_commits) + ')')
    print('forks with unique commits: ' + str(len(unique_commits)) + '/' + str(len(forks)))
    for k in sorted(unique_commits,key=lambda param:len(unique_commits[param])):
        print(k+':'+str(unique_commits[k]))