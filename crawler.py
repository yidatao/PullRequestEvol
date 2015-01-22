import requests
import json,re,os,subprocess,sys
import util,stats,db
from subprocess import CalledProcessError

#list of (commit, pullreq, evol, forkrepo)
def get_fork_repo(owner, project):
    pullreq = db.get_pullreq(owner,project)
    author_forks = get_all_forks(owner,project)

    #DOC: https://developer.github.com/v3/pulls/#list-commits-on-a-pull-request
    for pullID in pullreq:
        #test
        if pullID == '11':
            continue
        req_commit = requests.get('https://api.github.com/repos/' + owner + '/' + project + '/pulls/' + pullID + '/commits',auth=(username, pwd))
        data = json.loads(req_commit.text)

        pcommits = []
        for i in range(len(data)):
            pcommits.append(data[i]['sha'])

        #Some results, e.g., 428, has no author login info. Now we simply skip it
        if data[0]['author'] == None:
            print('no author: ' + pullID)
            continue
        #assume that one pull request, no matter how many commits are involved, only has one author
        author = data[0]['author']['login']
        #if the author is not in the forked repo's list
        if author not in author_forks:
            continue
        db.insert_forkrepo(author,author_forks[author],owner+'/'+project,pullID,pcommits)

#get commits from upstream and forks, and their branches. Then insert to commit table
def get_branches(author,project):
    upstream_commits = db.get_commits(author,project,False)
    os.chdir('D:/git_repo/' + author + '-' + project)
    for uc in upstream_commits:
        branches = get_commit_branch(uc)
        if len(branches) > 0:
            db.insert_commits(uc,author,project,0,branches)

    forkrepo = db.get_forkrepo(author+'/'+project)
    for f in forkrepo:
        fork_commits = db.get_commits(f[0],f[1],True)
        os.chdir('D:/git_repo/' + f[0] + '-' + f[1])
        for fc in fork_commits:
            fbranches = get_commit_branch(fc)
            if len(fbranches) > 0:
                db.insert_commits(fc,f[0],f[1],1,fbranches)


#find which branch a commit is made
def get_commit_branch(commit):
    branches = []
    try:
        output = subprocess.check_output('git branch --contains ' + commit, stderr=subprocess.STDOUT)
    except CalledProcessError as e:
        print(str(e.returncode) + ': ' + commit + ' not in any branch')
        return []
        pass
    lines = []
    try:
        lines = output.decode().split('\n')
    except:
        pass
    for line in lines:
        l = line.strip()
        if len(l) == 0:
            continue
        if l.startswith('*'):
            branches.append(l[2:])
        else:
            branches.append(l)
    return branches

#clone upstream and fork repo, checkout all branches
def setup_local_repo(author, project):
    forks = db.get_forkrepo(author+'/'+project)
    #for the given upstream, clone it and all its forks that have pull request
    os.chdir('D:/git_repo')
    #clone the upstream
    clone_repo(author,project)
    #clone its forks
    for f in forks:
        clone_repo(f[0],f[1])

    #for all these repo, checkout all their branches
    os.chdir('D:/git_repo/' + author + '-' + project)
    checkout_all_branches()
    for f in forks:
        os.chdir('D:/git_repo/' + f[0] + '-' + f[1])
        checkout_all_branches()


def checkout_all_branches():
    #get all branches
    branches = []
    output = subprocess.check_output('git branch -a', stderr=subprocess.STDOUT)
    lines = []
    try:
        lines = output.decode().split('\n')
    except:
        pass
    local_branches = [] #those branches that are already checked out
    for line in lines:
        l = line.strip()
        if len(l) == 0:
            continue
        if not l.startswith('remotes/'):
            if l.startswith('*'):
                local_branches.append(l[2:])
            else:
                local_branches.append(l)
        if '->' in l:
            continue
        if l.startswith('remotes/') and l != 'remotes/origin/master':
            remotebranch = l[l.rfind('/')+1:]
            if remotebranch not in local_branches:
                branches.append(remotebranch)
    print(str(len(local_branches))+' local branches')
    print(str(len(branches)) + ' branches checked out')

    for b in branches:
        retcode = subprocess.call('git checkout ' + b)
        if retcode != 0:
            print("checkout branch failed: " + b)
            sys.exit(0)


#clone git repo
def clone_repo(repo_owner,repo_name):
    #if the repo is already cloned
    if os.path.isdir(repo_owner+'-'+repo_name):
        return
    cmd = 'git clone https://github.com/' + repo_owner + '/' + repo_name + ' ' + repo_owner + '-' + repo_name
    retcode = subprocess.call(cmd)
    if retcode != 0:
        print("clone failed: " + repo_owner +'/'+repo_name)
        sys.exit(0)
    print('cloned ' + repo_owner + '-' + repo_name)

#get all the pull request and corresponding commit for the origin project
def get_pullreq_mergecommit(author,project):
    lastSHA = ''
    while True:
        startSHA = lastSHA
        #TODO not sure this github API lists all the commits
        url = 'https://api.github.com/repos/'+author+'/'+project+'/commits'
        if startSHA != '':
            url = url + '?sha='+startSHA

        r = requests.get(url,auth=(username, pwd))
        data = json.loads(r.text)
        for i in range(len(data)):
            msg = data[i]['commit']['message']
            mergecommit = data[i]['sha']
            p = re.compile('^Merge pull request #[0-9]+')
            m = p.match(msg)
            if m:
                match = m.group()
                pullID = match[match.find('#')+1:]
                db.insert_pullreq(author,project,pullID,mergecommit)
            lastSHA = mergecommit

        if lastSHA == startSHA:
            break


#get all the commits of upstream repo
def get_all_commits_in_upstream(author, project):
    allcommits = []
    os.chdir('D:/git_repo/'+author+'-'+project)
    #list all the commits in all branches
    cmd = 'git rev-list --remotes'
    output = subprocess.check_output(cmd)
    for l in output.decode().split('\n'):
        if len(l) > 0:
            allcommits.append(l.strip())
    return allcommits


#given a commit and its repo, find its later commits that change the same part
def get_commit_evol(commit, author, repo):
    os.chdir('D:/git_repo/'+author+'-'+repo)
    diffcmd = 'git diff -w --unified=0 ' + commit + '^ ' + commit
    #it's weird that if 'shell=True' is added as the parameter, the output is None
    output = subprocess.check_output(diffcmd, stderr=subprocess.STDOUT)
    diff = []
    try:
        diff = output.decode().split('\n')
    except:
        pass
    diffdetail = util.get_diff_detail(diff)
    branches = db.get_branches(commit,author,repo)

    evol = []
    for file in diffdetail:
        cmap = {}
        for b in branches:
            line_cursor = util.flatten(diffdetail[file].newlines)
            children = get_child_commit(commit, file, b)
            for c in children:
                cdiff = util.get_file_change_lines(c[0], file, 0)
                if util.is_overlap(line_cursor,cdiff):
                    #remove same commits in different branches. master branch is priority, then the branch that is first encountered
                    if c[0] in cmap:
                        if cmap[c[0]] != 'master' and c[1] == 'master':
                            cmap[c[0]] = 'master'
                    else:
                        cmap[c[0]] = c[1]
                line_cursor = util.get_lines_after_commit(line_cursor, cdiff)
        for k,v in cmap.items():
            evol.append((k,v,file))
    return evol

#(commit,pullreq,evolution) in the upstream repo
def get_evolution():
    commit_repo = db.get_commit_repo()
    for c in commit_repo:
        #test
        # if (not c[0].startswith('4c1758')) or c[1] != 'avandeursen':
        #     continue
        evol = get_commit_evol(c[0],c[1],c[2])
        db.update_evolution(c[0],c[1],evol)
        print(c)

#get all the commits after the given commit in branch b, in chronological order
def get_child_commit(commit, file, b):
    children = []
    #switch to the branch where the commit is in
    #subprocess.call('git commit -am \"test\"')
    retcode = subprocess.call('git checkout ' + b)
    if retcode != 0:
        print("checkout branch failed: " + b)
        sys.exit(0)

    cmd = 'git log --pretty=format:%h ' + commit + '.. --reverse -- ' + file
    output = subprocess.check_output(cmd)
    for l in output.decode().split('\n'):
        if len(l) > 0:
            children.append((l,b))
    return children

#since a fork might have a different name than the origin repo, like coreyjv/junit-team, we list all the forks for the origin
def get_all_forks(author, upstream):
    per_page = 70
    page = 1
    author_fork = {}
    while True:
        parameter = {'page':page,'per_page':per_page}
        req = requests.get('https://api.github.com/repos/'+author+'/'+upstream+'/forks',params=parameter, auth=(username, pwd))
        data = json.loads(req.text)
        for i in range(len(data)):
            f = data[i]['html_url']
            fork = f[len('https://github.com/'):]
            author_fork[fork[:fork.find('/')]] = fork[fork.find('/')+1:]
        if len(data) < per_page:
            break
        page += 1
    print(author+'/'+upstream+':'+str(len(author_fork))+' forks')
    return author_fork


if __name__ == "__main__":
    args = sys.argv
    username, pwd = args[0], args[1]
    # mergecommits = getMergeCommits()
    # print("merged pull request: " + str(len(mergecommits)))
    # pullcommits = getPullCommits(list(mergecommits.keys()))
    #repo = os.path.abspath(os.path.join(os.getcwd(), "../git_repo/junit"))
    #getCommitEvol('34a2e246efe2d9513f95ebbc873b2e8f1e1fc230','D:/git_repo/junit')
    # result = getForkEvol(['796'])
    # print(result)
    #pullreq_merge = getMergeCommits()
    #print('# of pull request: ' + str(len(pullreq_merge)))
    # upstream_evol = getUpstreamEvol(pullreq_merge)
    # print(upstream_evol)
    # stats.merge_evolution(upstream_evol)
    #getCommitBranch('fb7925bf75ffe9f802f54e2d717af11b58c75725','based2','junit')
    #getForkEvol('junit-team','junit',pullreq_merge.keys())
    #db.create_pullreq()
    #get_pullreq_mergecommit('junit-team','junit')
    #db.create_forkrepo()
    #get_fork_repo('junit-team','junit')
    #db.create_commit()
    #get_branches('junit-team','junit')
    #get_evolution()
    stats.get_unique_evol()