from collections import namedtuple
import subprocess

#given a diff output (list of lines), return the changed files and changed lines
def get_diff_detail(diff):
    result = namedtuple('result','oldlines newlines')
    filelines = {}
    curfile = ''
    oldline = []
    newline = []
    flag = False
    for line in diff:
        if line.startswith('--- a/'):
            #store the previous file & reset the curfile and curline
            if len(curfile) > 0:
                filelines[curfile] = result(oldline,newline)
            curfile = line[6:]
            oldline = []
            newline = []
        if line.startswith('--- /dev/null'):
            flag = True
        if flag and line.startswith('+++ b/'):
            if len(curfile) > 0:
                filelines[curfile] = result(oldline,newline)
            curfile = line[6:]
            oldline = []
            newline = []
            flag = False
        if line.startswith('@@ '):
            lines = get_line_number(line)
            #oldline/newline might be empty (), but we don't check this to ensure they are in pairs
            oldline.append(lines.oldline)
            newline.append(lines.newline)
    #the last file
    filelines[curfile] = result(oldline,newline)
    return filelines

#given a line starts with @@, get its diff line numbers
def get_line_number(line):
        rawline = ''
        if line.find(' @@ ') > -1:
            rawline = line[3:line.find(' @@ ')]
        else:
            rawline = line[3:line.find(' @@')]
        half1 = rawline[1:rawline.find(' +')]
        half2 = rawline[rawline.find(' +')+2:]


        #tuple (start-line, end-line)
        oldline = ()
        if ',' in half1:
            count = int(half1[half1.find(',')+1:])
            if not count == 0:
                startline = int(half1[:half1.find(',')])
                oldline = (startline, startline + count -1)
        else:
            oldline = (int(half1), int(half1))

        newline = ()
        if ',' in half2:
            count = int(half2[half2.find(',')+1:])
            if not count == 0:
                startline = int(half2[:half2.find(',')])
                newline = (startline,startline + count -1)
        else:
            newline = (int(half2), int(half2))

        result = namedtuple("result", "oldline newline")
        return result(oldline, newline)

#get all the changed lines in the given file in the given commit
def get_file_change_lines(commit_hash, file, context):
    #list of range tuple (startline, endline)
    old_line_range = []
    new_line_range = []
    #TODO not sure we should switch branch here (maybe not, cuz now it's in the right branch). Also this call should belong to crawler instead of util
    cmd = 'git show -w --unified=' + str(context) + ' --pretty=format:b% ' + commit_hash + ' -- ' + file
    output = subprocess.check_output(cmd, shell=True)
    diff = []
    try:
        diff = output.decode().split('\n')
    except:
        pass
    for line in diff:
        if line.startswith('@@ '):
            lines = get_line_number(line)
            old_line_range.append(lines.oldline)
            new_line_range.append(lines.newline)

    result = namedtuple('result', 'oldlines newlines')
    return result(old_line_range,new_line_range)

#if the target lines are changed in the given commit/diff
def is_overlap(target_line, diff):
    # the target lines are the same as the oldlines in text diff
    for l in diff.oldlines:
        if len(l) == 0:
            continue
        for lc in target_line:
            if l[0] <= lc <= l[1]:
                return True
    return False


#check if target lines are changed in the given commit; also, return its corresponding lines after this commit
def get_lines_after_commit(target_lines, diff):
    hunkcount = len(diff.oldlines)
    for i in range(hunkcount):
        oldline = diff.oldlines[i]
        newline = diff.newlines[i]
        # only new lines are added
        if len(oldline) == 0:
            target_lines = refresh_target_lines(newline[0], newline[1]-newline[0]+1, target_lines, 'case1')
        # only lines are deleted
        elif len(newline) == 0:
            target_lines = refresh_target_lines(oldline[0], oldline[1]-oldline[0]+1, target_lines, 'case2')
        else:
            # update the subsequent target lines (if oldrange = newrange, then no impact)
            oldrange = oldline[1] - oldline[0] + 1
            newrange = newline[1] - newline[0] + 1
            if newrange > oldrange:
                # equal to from old endline+1 add the differnce of the range
                target_lines = refresh_target_lines(newline[0] + oldrange, newrange - oldrange, target_lines, 'case1')
            elif oldrange > newrange:
                # equal to from new endline+1 delete the difference of the range
                target_lines = refresh_target_lines(newline[1]+1, oldrange - newrange, target_lines, 'case2')

    return target_lines

def refresh_target_lines(start, range, target_lines, case):
    new_target_lines = []
    if case == "case1":
        for l in target_lines:
            # all lines after increase by range
            if l >= start:
                new_target_lines.append(l+range)
            else:
                new_target_lines.append(l)
    if case == "case2":
        for l in target_lines:
            if l > start + range - 1:
                new_target_lines.append(l-range)
            elif l < start:
                new_target_lines.append(l)
            # if l inbetween, then it's simply deleted

    return new_target_lines

def flatten(lines):
    flat_lines = []
    for l in lines:
        if len(l) == 0:
            continue
        flat_lines = flat_lines + [i for i in range(l[0],l[1]+1)]
    return flat_lines

def write_to_file(file, content):
    f = open(file, 'w')
    f.write(content)
    f.close()