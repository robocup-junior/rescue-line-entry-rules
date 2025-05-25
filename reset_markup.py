import re, textwrap, glob, sys

DELETION_REGEXP = re.compile(r'\{--(.*?)--\}', re.DOTALL)
ADDITION_REGEXP = re.compile(r'\{\+\+(.*?)\+\+\}', re.DOTALL)
SUBSTITUTION_REGEXP = re.compile(r'\{~~(.*?)~>(.*?)~~\}', re.DOTALL)

class Deletor:

    def __init__(self, changes, note_fmt, replacement_fmt, reset_markup):
        self.changes = changes
        self.note_fmt = note_fmt
        self.replacement_fmt = replacement_fmt
        self.reset_markup = reset_markup

    def __call__(self, match):
        global n_deletions
        n_deletions += 1

        def callback(n_deletions, match):
            global first_change, change_header
            m = match.group(1).replace('\n', ' ')
            txt = self.replacement_fmt.replace('{PREVIOUS}', m)
            note = self.note_fmt.replace('{PREVIOUS}', m)
            change_id = f'deletion-{n_deletions}'
            self.changes.append(change_id)
            if self.reset_markup:
                return f'{txt}'
            if change_header == True:
                change_header = False
                return f'{txt} [[{change_id}, {note}]]'
            elif first_change == True:
                first_change = False
                return f'\n[[{change_id}, {note}]]{txt}'
            else:
                return f'[[{change_id}, {note}]]{txt}'

        return callback(n_deletions, match)


class Additor:

    def __init__(self, changes, note_fmt, replacement_fmt, reset_markup):
        self.changes = changes
        self.note_fmt = note_fmt
        self.replacement_fmt = replacement_fmt
        self.reset_markup = reset_markup

    def __call__(self, match):
        global n_additions
        n_additions += 1

        def callback(n_additions, match):
            global first_change, change_header
            m = match.group(1).replace('\n', ' ')
            txt = self.replacement_fmt.replace('{CURRENT}', m)
            note = self.note_fmt.replace('{CURRENT}', m)
            change_id = f'addition-{n_additions}'
            self.changes.append(change_id)
            if self.reset_markup:
                return f'{txt}'
            if change_header == True:
                change_header = False
                return f'{txt} [[{change_id}, {note}]]'
            elif first_change == True:
                first_change = False
                return f'\n[[{change_id}, {note}]]{txt}'
            else:
                return f'[[{change_id}, {note}]]{txt}'

        return callback(n_additions, match)


class Substituter:

    def __init__(self, changes, note_fmt, replacement_fmt, reset_markup,
                 wrap_long_strings_at=None):
        self.changes = changes
        self.note_fmt = note_fmt
        self.replacement_fmt = replacement_fmt
        self.reset_markup = reset_markup
        self.wrap_long_strings_at = wrap_long_strings_at

    def shorten(self, string):
        if self.wrap_long_strings_at is not None:
            return textwrap.shorten(string,
                                    self.wrap_long_strings_at,
                                    placeholder='...')
        return string

    def __call__(self, match):
        global n_substitutions
        n_substitutions += 1

        def callback(n_substitutions, match):
            global first_change, change_header
            previous = match.group(1).replace('\n', ' ')
            current = match.group(2).replace('\n', ' ')

            short_previous = self.shorten(previous)
            short_current = self.shorten(current)

            txt = self.replacement_fmt.replace('{CURRENT}', current) \
                                      .replace('{PREVIOUS}', previous)
            note = self.note_fmt.replace('{CURRENT}', short_current) \
                                .replace('{PREVIOUS}', short_previous)

            change_id = f'substitution-{n_substitutions}'
            self.changes.append(change_id)
            if self.reset_markup:
                return f'{txt}'
            if change_header == True:
                change_header = False
                return f'{txt} [[{change_id}, {note}]]'
            elif first_change == True:
                first_change = False
                return f'\n[[{change_id}, {note}]]{txt}'
            else:
                return f'[[{change_id}, {note}]]{txt}'
    

        return callback(n_substitutions, match)


class CriticMarkupPreprocessor:

    def __init__(self,
                 change_listing_fmt='- {CHANGE}',
                 addition_note_fmt='Added "{CURRENT}"',
                 addition_replacement_fmt='{CURRENT}',
                 deletion_note_fmt='Deleted "{PREVIOUS}"',
                 deletion_replacement_fmt='(used to be "{PREVIOUS}")',
                 substitution_note_fmt='Changed "{PREVIOUS}" to "{CURRENT}"',
                 substitution_replacement_fmt='{CURRENT} (used to be "{PREVIOUS}")',
                 reset_markup=False): # noqa
        self.changes = []
        self.change_listing_fmt = change_listing_fmt
        self.addition_note_fmt = addition_note_fmt
        self.addition_replacement_fmt = addition_replacement_fmt
        self.deletion_note_fmt = deletion_note_fmt
        self.deletion_replacement_fmt = deletion_replacement_fmt
        self.substitution_note_fmt = substitution_note_fmt
        self.substitution_replacement_fmt = substitution_replacement_fmt
        self.reset_markup = reset_markup

    def convert(self, infile):
        global first_change, change_header
        d = Deletor(self.changes,
                    self.deletion_note_fmt,
                    self.deletion_replacement_fmt,
                    self.reset_markup)
        a = Additor(self.changes,
                    self.addition_note_fmt,
                    self.addition_replacement_fmt,
                    self.reset_markup)
        s = Substituter(self.changes,
                        self.substitution_note_fmt,
                        self.substitution_replacement_fmt,
                        self.reset_markup)
        
        with open(infile) as f:
            inlines = f.readlines()
            outfile = ""
            for instr in inlines:
                match_indexes = []
                match_indexes += [["d", m.start()] for m in re.finditer(DELETION_REGEXP,instr)]
                match_indexes += [["a", m.start()] for m in re.finditer(ADDITION_REGEXP,instr)]
                match_indexes += [["s", m.start()] for m in re.finditer(SUBSTITUTION_REGEXP,instr)]
                sorted_index = sorted(match_indexes, key=lambda x: (x[1]))
                for change, match in enumerate(sorted_index):
                    if (change == 0 and bool(re.match('^\W+\s+\S+.*{',instr)) == True):
                        first_change = True
                    else:
                        first_change = False
                    if bool(re.match('^=',instr)) == True:
                        change_header = True
                    else:
                        change_header = False
                    if match[0] == "d":
                        instr = DELETION_REGEXP.sub(d, instr)
                    if match[0] == "a":
                        instr = ADDITION_REGEXP.sub(a, instr)
                    if match[0] == "s":
                        instr = SUBSTITUTION_REGEXP.sub(s, instr)
                outfile += instr
        list_of_changes = [self.change_listing_fmt.replace('{CHANGE}',change) for change in self.changes]

        return outfile, list_of_changes

def getfiles():
    adoc_files = sorted(glob.glob('*.adoc'))
    adoc_files = adoc_files[-1:] + adoc_files[:-1]
    return adoc_files

def writeTOC(rule_file, list_of_changes):
    with open(rule_file, "r+") as rf:
        instr = rf.read()
        changes = '\n'.join(list_of_changes)
        instr = instr.replace('{+-~TOC-CHANGES~-+}', changes)
        rf.seek(0)
        rf.write(instr)

def createMarkupPreproc(reset) -> CriticMarkupPreprocessor:
    if reset:
        cmp = CriticMarkupPreprocessor(
            #change_listing_fmt='- <<{CHANGE}>>',
            #addition_note_fmt='Added "{CURRENT}"',
            addition_replacement_fmt='{CURRENT}',
            #deletion_note_fmt='Deleted "{PREVIOUS}"',
            deletion_replacement_fmt='', # noqa
            #substitution_note_fmt='Changed "{PREVIOUS}" to "{CURRENT}"',
            substitution_replacement_fmt='{CURRENT}', # noqa
            reset_markup=True
        )
    else:
        cmp = CriticMarkupPreprocessor(
            change_listing_fmt='- <<{CHANGE}>>',
            addition_note_fmt='Added "{CURRENT}"',
            addition_replacement_fmt='[red]#*{CURRENT}*#',
            deletion_note_fmt='Deleted "{PREVIOUS}"',
            deletion_replacement_fmt='footnote:[In previous version this said "{PREVIOUS}"]', # noqa
            substitution_note_fmt='Changed "{PREVIOUS}" to "{CURRENT}"',
            substitution_replacement_fmt='[red]#*{CURRENT}*#\nfootnote:[In previous version this said "{PREVIOUS}"]' # noqa
        )
    return cmp
    
if __name__ == '__main__':
    reset_markup = False
    
    if len(sys.argv) == 2 and sys.argv[1] == "-r":
        reset_markup = True    
        
    cmp = createMarkupPreproc(reset_markup)
    
    n_deletions = 0
    n_additions = 0
    n_substitutions = 0

    adoc_files = getfiles()
    for file in adoc_files:
        changed_file, list_of_changes = cmp.convert(file)
        with open(file, "w") as cf:
            cf.write(changed_file)
    if not reset_markup:
        writeTOC(adoc_files[0],list_of_changes)