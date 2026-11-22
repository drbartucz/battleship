'''Battleship tournament.

Run this file to play every strategy against every other strategy:

    python run_tournament.py                    strategies + examples (for practice)
    python run_tournament.py --watch            the same, but show the boards for every game
    python run_tournament.py --versus rando     watch one game: your strategy against "rando"
    python run_tournament.py --versus rando checkers      watch one game between those two
    python run_tournament.py --versus rando --speed 3     slower: 3 shots a second
    python run_tournament.py --versus rando --games 20    a series of 20 games
    python run_tournament.py --no-examples      only the "strategies" folder (the real thing)
    python run_tournament.py --check            only check the files, don't play
    python run_tournament.py --seconds 120      stretch the tournament out to about 2 minutes
    python run_tournament.py some_folder        play the strategies in other folder(s)

Every .py file in the folder is one player, whatever the file is called.
Each file needs:

    strategy_name = 'Something unique'
    def take_shot(board, ships_left):       # returns (row, column)

and may also have:

    def place_ships(ship_lengths):          # returns a list of (row, column, direction)

The standings update on screen after every game and are saved to results.txt.
'''
import argparse
import concurrent.futures
import contextlib
import datetime
import importlib.util
import io
import itertools
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ----------------------------------------------------------------------------
# Settings you might want to change
# ----------------------------------------------------------------------------
SIZE = 10                       # the board is SIZE rows by SIZE columns
SHIPS = [5, 4, 3, 3, 2]         # the length of each ship in a fleet
GAMES_PER_PAIR = 10             # each pair of players meets this many times
MAX_SHOTS = 200                 # a player who still hasn't won after this many turns stops
STUCK_AFTER_SECONDS = 5         # a file that runs longer than this in the pre-start check is left out

DEMO_FILENAME = 'demo_strategy.py'
DEMO_NAME = 'Demo Strategy'
MAX_NAME_LENGTH = 24
RESULTS_FILENAME = 'results.txt'

# What a strategy sees in each square of the board it is shooting at.
UNKNOWN, MISS, HIT, SUNK = '.', 'M', 'H', 'S'
ACROSS, DOWN = 'across', 'down'

HERE = Path(__file__).resolve().parent
QUIET = io.StringIO()           # print()s from strategies go here instead of the screen


class Player:
    def __init__(self, name, file, take_shot, place_ships, source):
        self.name = name
        self.file = file                # e.g. 'strategies/maria.py'
        self.take_shot = take_shot
        self.place_ships = place_ships  # None if the file leaves placement to chance
        self.source = source
        self.is_baseline = Path(file).name.casefold() == DEMO_FILENAME
        self.is_example = file.startswith('examples/')
        self.wins = self.losses = self.draws = 0
        self.shots_in_wins = 0
        self.bad_shots = 0
        self.bad_placements = 0
        self.first_error = ''
        self.versus = {}                # opponent Player -> [wins, losses, draws]

    @property
    def label(self):
        return self.name + ' (baseline)' if self.is_baseline else self.name

    @property
    def games(self):
        return self.wins + self.losses + self.draws

    @property
    def win_percent(self):
        return 100 * (self.wins + self.draws / 2) / self.games if self.games else 0.0

    @property
    def shots_per_win(self):
        return self.shots_in_wins / self.wins if self.wins else 0.0

    def note_error(self, error):
        self.first_error = self.first_error or error


# ----------------------------------------------------------------------------
# The game
# ----------------------------------------------------------------------------
def ship_cells(row, column, direction, length):
    if direction == ACROSS:
        return [(row, column + i) for i in range(length)]
    return [(row + i, column) for i in range(length)]


def random_fleet():
    '''Put every ship somewhere at random. Ships may touch but never overlap.'''
    taken, fleet = set(), []
    for length in SHIPS:
        while True:
            direction = random.choice([ACROSS, DOWN])
            row = random.randrange(SIZE - (length - 1 if direction == DOWN else 0))
            column = random.randrange(SIZE - (length - 1 if direction == ACROSS else 0))
            cells = ship_cells(row, column, direction, length)
            if not taken.intersection(cells):
                break
        taken.update(cells)
        fleet.append({'cells': cells, 'hits': set()})
    return fleet


def fleet_from_answer(answer):
    '''Turn what place_ships() returned into a fleet. Return (fleet, error).'''
    if not isinstance(answer, (list, tuple)) or len(answer) != len(SHIPS):
        return None, 'place_ships() must return a list of {} ships, but returned {!r}'.format(len(SHIPS), answer)
    taken, fleet = set(), []
    for length, ship in zip(SHIPS, answer):
        if not isinstance(ship, (list, tuple)) or len(ship) != 3:
            return None, 'each ship must be (row, column, direction), but one was {!r}'.format(ship)
        row, column, direction = ship
        direction = direction.strip().lower() if isinstance(direction, str) else direction
        if type(row) is not int or type(column) is not int or direction not in (ACROSS, DOWN):
            return None, "each ship must be (row, column, 'across' or 'down'), but one was {!r}".format(ship)
        cells = ship_cells(row, column, direction, length)
        if any(not (0 <= r < SIZE and 0 <= c < SIZE) for r, c in cells):
            return None, 'the ship of length {} at {!r} sticks out of the board'.format(length, ship)
        if taken.intersection(cells):
            return None, 'the ship of length {} at {!r} overlaps another ship'.format(length, ship)
        taken.update(cells)
        fleet.append({'cells': cells, 'hits': set()})
    return fleet, ''


def describe_error(error):
    return '{}: {}'.format(type(error).__name__, error)


def call_quietly(function, *arguments):
    '''Call a strategy's function with its print()s hidden. Return (answer, error).'''
    screen, sys.stdout = sys.stdout, QUIET
    try:
        return function(*arguments), ''
    except Exception as error:
        return None, 'crashed with ' + describe_error(error)
    finally:
        sys.stdout = screen
        QUIET.seek(0)
        QUIET.truncate()


def ask_for_fleet(player):
    '''Return (fleet, error). A player with no (or a broken) place_ships() gets a random fleet.'''
    if player.place_ships is None:
        return random_fleet(), ''
    answer, error = call_quietly(player.place_ships, list(SHIPS))
    if error:
        return random_fleet(), 'place_ships() ' + error
    fleet, error = fleet_from_answer(answer)
    return (fleet, '') if fleet else (random_fleet(), error)


def ask_for_shot(player, view, ships_left):
    '''Return ((row, column), error). The shot is None if it cannot be used.'''
    answer, error = call_quietly(player.take_shot, [row[:] for row in view], list(ships_left))
    if error:
        return None, 'take_shot() ' + error
    if not isinstance(answer, (list, tuple)) or len(answer) != 2 \
            or type(answer[0]) is not int or type(answer[1]) is not int:
        return None, 'take_shot() returned {!r} instead of (row, column)'.format(answer)
    row, column = answer
    if not (0 <= row < SIZE and 0 <= column < SIZE):
        return None, 'take_shot() returned ({}, {}), which is off the board'.format(row, column)
    if view[row][column] != UNKNOWN:
        return None, 'take_shot() returned ({}, {}), which it had already shot at'.format(row, column)
    return (row, column), ''


class Game:
    '''One game between two players. players[0] shoots first.'''

    def __init__(self, player1, player2):
        self.players = (player1, player2)
        self.fleets = []
        for player in self.players:
            fleet, error = ask_for_fleet(player)
            if error:
                player.bad_placements += 1
                player.note_error(error)
            self.fleets.append(fleet)
        # views[i] is what players[i] knows about the board they are shooting at
        self.views = [[[UNKNOWN] * SIZE for _ in range(SIZE)] for _ in self.players]
        self.shots = [0, 0]
        self.hits = [0, 0]
        self.last = [None, None]        # each player's most recent shot
        self.winner = None              # 0, 1, or 'draw' once the game is over

    def ships_left(self, shooter):
        return sorted((len(ship['cells']) for ship in self.fleets[1 - shooter]
                       if len(ship['hits']) < len(ship['cells'])), reverse=True)

    def take_turn(self, shooter):
        player, view, fleet = self.players[shooter], self.views[shooter], self.fleets[1 - shooter]
        self.shots[shooter] += 1
        shot, error = ask_for_shot(player, view, self.ships_left(shooter))
        self.last[shooter] = shot
        if error:
            player.bad_shots += 1
            player.note_error(error)
            return
        row, column = shot
        view[row][column] = MISS
        for ship in fleet:
            if shot in ship['cells']:
                ship['hits'].add(shot)
                self.hits[shooter] += 1
                view[row][column] = HIT
                if len(ship['hits']) == len(ship['cells']):
                    for r, c in ship['cells']:
                        view[r][c] = SUNK
        if not self.ships_left(shooter):
            self.winner = shooter

    def play(self, after_each_shot=None):
        while self.winner is None:
            for shooter in (0, 1):
                self.take_turn(shooter)
                if after_each_shot:
                    after_each_shot(self)
                if self.winner is not None:
                    break
            else:
                if self.shots[1] >= MAX_SHOTS:      # nobody managed to finish: most hits wins
                    self.winner = 0 if self.hits[0] > self.hits[1] else \
                        1 if self.hits[1] > self.hits[0] else 'draw'
        self.record()
        return self

    def record(self):
        for me in (0, 1):
            player, opponent = self.players[me], self.players[1 - me]
            tally = player.versus.setdefault(opponent, [0, 0, 0])
            if self.winner == 'draw':
                player.draws += 1
                tally[2] += 1
            elif self.winner == me:
                player.wins += 1
                player.shots_in_wins += self.shots[me]
                tally[0] += 1
            else:
                player.losses += 1
                tally[1] += 1

    def summary(self):
        first, second = self.players
        if self.winner == 'draw':
            return '{} and {} drew'.format(first.name, second.name)
        winner, loser = self.players[self.winner], self.players[1 - self.winner]
        return '{} beat {} in {} shots'.format(winner.name, loser.name, self.shots[self.winner])


# ----------------------------------------------------------------------------
# Loading and checking the strategy files
# ----------------------------------------------------------------------------
def simplify(name):
    '''"Demo  Strategy", "demo_strategy" and "DEMOSTRATEGY" all count as the same name.'''
    return re.sub(r'[\W_]+', '', name).casefold()


def is_stuck(path):
    '''Try the file out in a separate Python, which can be stopped if it never finishes.'''
    try:
        subprocess.run([sys.executable, str(Path(__file__).resolve()), '--probe', str(path)],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=STUCK_AFTER_SECONDS)
    except subprocess.TimeoutExpired:
        return True
    return False


def probe(path):
    '''Runs inside that separate Python: load one file and let it play a few games by itself.'''
    spec = importlib.util.spec_from_file_location('probe', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    player = Player('probe', str(path), module.take_shot, getattr(module, 'place_ships', None), '')
    for _ in range(3):
        Game(player, player).play()


def load_strategies(folders):
    '''Return (players, problems, warnings). Files with problems do not play.'''
    players, problems, warnings = [], [], []
    paths = []
    for folder in folders:
        if not folder.is_dir():
            problems.append((str(folder), 'this folder does not exist'))
            continue
        paths += [(folder, number, path) for number, path in enumerate(sorted(folder.glob('*.py')))
                  if not path.name.startswith('_')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        stuck = list(pool.map(is_stuck, [path for _, _, path in paths]))

    for (folder, number, path), file_is_stuck in zip(paths, stuck):
        label = folder.name + '/' + path.name
        if folder.parent.name == 'examples':        # a folder inside examples is still examples
            label = 'examples/' + label
        if file_is_stuck:
            problems.append((label, 'the code ran for more than {} seconds without finishing - '
                             'look for a loop that never ends'.format(STUCK_AFTER_SECONDS)))
            continue
        try:
            source = path.read_text(encoding='utf-8', errors='replace')
            spec = importlib.util.spec_from_file_location(
                'strategy_{}_{}'.format(simplify(folder.name), number), path)
            module = importlib.util.module_from_spec(spec)
            with contextlib.redirect_stdout(io.StringIO()):
                spec.loader.exec_module(module)
        except KeyboardInterrupt:
            raise
        except BaseException as error:     # includes SyntaxError and exit()
            line = getattr(error, 'lineno', None)
            where = ' (line {})'.format(line) if line else ''
            problems.append((label, 'Python could not run this file{} - {}'.format(
                where, describe_error(error))))
            continue

        name = getattr(module, 'strategy_name', None)
        take_shot = getattr(module, 'take_shot', None)
        place_ships = getattr(module, 'place_ships', None)
        if not isinstance(name, str) or not name.strip():
            problems.append((label, "needs a line like  strategy_name = 'Your Name'"))
            continue
        if not callable(take_shot):
            problems.append((label, 'needs a function called take_shot()'))
            continue
        name = ' '.join(name.split())
        if len(name) > MAX_NAME_LENGTH:
            warnings.append((label, 'strategy_name is long, so it was cut to "{}"'.format(
                name[:MAX_NAME_LENGTH])))
            name = name[:MAX_NAME_LENGTH].strip()
        players.append(Player(name, label, take_shot, place_ships if callable(place_ships) else None, source))

    # The demo file and the demo name belong together, and to nobody else.
    kept = []
    for player in players:
        is_demo_file = Path(player.file).name.casefold() == DEMO_FILENAME
        is_demo_name = simplify(player.name) == simplify(DEMO_NAME)
        if is_demo_file and not is_demo_name:
            problems.append((player.file, 'strategy_name was changed to "{}" but the file is still '
                             'called {} - rename the file'.format(player.name, DEMO_FILENAME)))
        elif is_demo_name and not is_demo_file:
            problems.append((player.file, 'the file was renamed but strategy_name is still '
                             '"{}" - change strategy_name'.format(player.name)))
        else:
            kept.append(player)

    # Every name must be unique.
    by_name = {}
    for player in kept:
        by_name.setdefault(simplify(player.name), []).append(player)
    players = []
    for group in by_name.values():
        if len(group) > 1:
            for player in group:
                others = ', '.join(p.file for p in group if p is not player)
                problems.append((player.file, 'strategy_name "{}" is also used by {} - names must '
                                 'be different'.format(player.name, others)))
        else:
            players.append(group[0])

    # Things worth knowing about, but which don't stop a strategy from playing.
    demo_code = [strip_name_line(p.source) for p in kept
                 if Path(p.file).name.casefold() == DEMO_FILENAME]
    for player in players:
        if demo_code and Path(player.file).name.casefold() != DEMO_FILENAME \
                and strip_name_line(player.source) == demo_code[0]:
            warnings.append((player.file, 'the code is still the same as the demo strategy'))
        empty = [[UNKNOWN] * SIZE for _ in range(SIZE)]
        shot, error = ask_for_shot(player, empty, SHIPS)
        if error:
            warnings.append((player.file, 'on an empty board, ' + error))
        if player.place_ships:
            answer, error = call_quietly(player.place_ships, list(SHIPS))
            error = 'place_ships() ' + error if error else fleet_from_answer(answer)[1]
            if error:
                warnings.append((player.file, error + ' (its ships will be placed at random instead)'))
    return players, problems, warnings


def strip_name_line(source):
    lines = [line.strip() for line in source.splitlines()]
    return [line for line in lines if line and not line.startswith('strategy_name')]


# ----------------------------------------------------------------------------
# Showing the boards
# ----------------------------------------------------------------------------
RESET = '\x1b[0m'
BOLD = '\x1b[1m'
DIM = '\x1b[2m'
WATER = '\x1b[44;94m'           # blue
AFLOAT = '\x1b[100;97m'         # grey: part of a ship that has not been hit
MISSED = '\x1b[44;97m'          # white on blue
STRUCK = '\x1b[41;97;1m'        # white on red
WRECK = '\x1b[40;91m'           # red on black: part of a sunk ship
LATEST = '\x1b[103;30;1m'       # black on yellow: the most recent shot
BOARD_WIDTH = 3 + 2 * SIZE
GAP = '           '


def board_lines(view, fleet, last):
    '''The board one player is shooting at, as a list of coloured lines.'''
    afloat = {cell for ship in fleet for cell in ship['cells']}
    lines = ['   ' + ''.join('{:<2}'.format(column) for column in range(SIZE))]
    for row in range(SIZE):
        line = '{:>2} '.format(row)
        for column in range(SIZE):
            mark = view[row][column]
            if mark == HIT:
                colour, text = STRUCK, 'X'
            elif mark == SUNK:
                colour, text = WRECK, '#'
            elif mark == MISS:
                colour, text = MISSED, 'o'
            elif (row, column) in afloat:
                colour, text = AFLOAT, '='
            else:
                colour, text = WATER, '~'
            if (row, column) == last:
                colour = LATEST
            line += colour + text + ' ' + RESET
        lines.append(line)
    return lines


def game_lines(game):
    '''Both boards side by side, each under the name of the player shooting at it.'''
    def pad(text):
        return '{:<{w}}'.format(text[:BOARD_WIDTH + len(GAP) - 1], w=BOARD_WIDTH + len(GAP))

    lines = ['   ' + BOLD + pad('Shots by ' + game.players[0].name) + pad('Shots by ' + game.players[1].name) + RESET,
             '   ' + ''.join(pad('shots {:<3} hits {:<2}'.format(game.shots[i], game.hits[i])) for i in (0, 1)),
             '   ' + ''.join(pad('still to sink: ' + (' '.join(map(str, game.ships_left(i))) or 'none!'))
                             for i in (0, 1)),
             '']
    left = board_lines(game.views[0], game.fleets[1], game.last[0])
    right = board_lines(game.views[1], game.fleets[0], game.last[1])
    lines += ['   ' + a + GAP + b for a, b in zip(left, right)]
    lines += ['',
              '   {}~ {} water   {}= {} ship   {}o {} miss   {}X {} hit   {}# {} sunk   {}  {} latest shot'.format(
                  WATER, RESET, AFLOAT, RESET, MISSED, RESET, STRUCK, RESET, WRECK, RESET, LATEST, RESET)]
    return lines


def draw(lines):
    '''Replace what is on the screen with these lines.'''
    width, height = shutil.get_terminal_size((100, 40))
    sys.stdout.write('\x1b[H' + ''.join(line + '\x1b[K\n' for line in lines[:height - 1]) + '\x1b[J')
    sys.stdout.flush()


def start_screen():
    os.system('')                       # switches on screen control codes in Windows terminals
    sys.stdout.write('\x1b[2J\x1b[?25l')   # clear the screen and hide the cursor


def end_screen():
    sys.stdout.write('\x1b[?25h')
    sys.stdout.flush()


# ----------------------------------------------------------------------------
# Standings and the results file
# ----------------------------------------------------------------------------
def standings(players):
    '''Best win percentage first; ties go to whoever needs fewer shots to win.'''
    return sorted(players, key=lambda p: (p.games == 0, -p.win_percent, p.shots_per_win, p.name.casefold()))


def prize_lines(players):
    '''Who wins a prize: the top three entries that finished above the baseline.'''
    ranked = standings(players)
    baseline = [p for p in ranked if p.is_baseline and p.games]
    entries = [p for p in ranked if not p.is_baseline and not p.is_example]
    if not baseline or not entries:
        return []
    above = [p for p in ranked[:ranked.index(baseline[0])] if not p.is_example]
    lines = ['', '   PRIZES go to the top three who finished above the baseline ({}):'.format(DEMO_NAME)]
    lines += ['      {}. {}'.format(place, p.name) for place, p in enumerate(above[:3], 1)]
    if len(above) < 3:
        lines.append('      Nobody else finished above the baseline.' if above else
                     '      Nobody finished above the baseline!')
    return lines


def leaderboard_lines(players, previous_ranks=None, limit=None):
    lines = ['       #  {:<{w}}  {:>5}  {:>4}  {:>4}  {:>5}  {:>9}'.format(
                 'Player', 'Win %', 'Won', 'Lost', 'Drawn', 'Shots/win', w=MAX_NAME_LENGTH),
             '      --  {}  {}  {}  {}  {}  {}'.format('-' * MAX_NAME_LENGTH, '-' * 5, '-' * 4, '-' * 4, '-' * 5, '-' * 9)]
    ranked = standings(players)
    for rank, player in enumerate(ranked[:limit], start=1):
        arrow = ' '
        if previous_ranks and player in previous_ranks:
            arrow = '▲' if rank < previous_ranks[player] else \
                    '▼' if rank > previous_ranks[player] else ' '
        lines.append('   {} {:>3}  {:<{w}}  {:>5.1f}  {:>4}  {:>4}  {:>5}  {:>9}'.format(
            arrow, rank, player.label, player.win_percent, player.wins, player.losses, player.draws,
            '{:.1f}'.format(player.shots_per_win) if player.wins else '-', w=MAX_NAME_LENGTH))
    if limit and len(ranked) > limit:
        lines.append('          ... and {} more (see {})'.format(len(ranked) - limit, RESULTS_FILENAME))
    return lines


def progress_lines(done, total, latest):
    bar_width = 30
    filled = bar_width * done // total
    return ['',
            '   BATTLESHIP TOURNAMENT',
            '',
            '   Game {} of {}  [{}{}]'.format(done, total, '#' * filled, '.' * (bar_width - filled)),
            '   Last result: ' + latest,
            '']


def trouble(players):
    notes = []
    for player in standings(players):
        if player.bad_shots or player.bad_placements:
            counts = ['{} wasted shots'.format(player.bad_shots)] if player.bad_shots else []
            counts += ['{} bad ship placements'.format(player.bad_placements)] if player.bad_placements else []
            notes.append((player.file, '{}. The first problem: {}'.format(' and '.join(counts), player.first_error)))
    return notes


def build_report(players, games_played, total_games, problems, warnings, status):
    ranked = standings(players)
    out = ['BATTLESHIP TOURNAMENT',
           datetime.datetime.now().strftime('%A %d %B %Y, %H:%M'),
           '{} - {} of {} games played'.format(status, games_played, total_games),
           '',
           'Board {} x {}, ships of length {}.'.format(SIZE, SIZE, ', '.join(map(str, SHIPS))),
           'Every pair plays {} games and takes turns to shoot first.'.format(GAMES_PER_PAIR),
           'Ranked by win %. Ties go to whoever needs fewer shots, on average, to win.',
           '', '=' * 80, 'LEADERBOARD', '=' * 80]
    out += leaderboard_lines(players)
    if status == 'FINAL RESULTS':
        out += prize_lines(players)

    for title, notes in (('FILES THAT COULD NOT PLAY', problems), ('WARNINGS', warnings),
                         ('WASTED SHOTS AND BAD SHIP PLACEMENTS', trouble(players))):
        if notes:
            out += ['', '=' * 80, title, '=' * 80]
            out += ['{}: {}'.format(file, message) for file, message in notes]

    out += ['', '=' * 80, 'WHO IS WHO', '=' * 80]
    out += ['{:>3}  {:<{w}}  {}'.format(i, p.name, p.file, w=MAX_NAME_LENGTH) for i, p in enumerate(ranked, 1)]

    out += ['', '=' * 80, 'HEAD TO HEAD', '=' * 80,
            'Each row shows how many games that player won against each opponent',
            '(the numbers across the top are the ranks from the leaderboard).', '']
    out.append(' ' * (MAX_NAME_LENGTH + 5) + ''.join('{:>5}'.format(i) for i in range(1, len(ranked) + 1)))
    for i, player in enumerate(ranked, 1):
        cells = ''.join('{:>5}'.format('-' if other is player else
                                       player.versus[other][0] if other in player.versus else '')
                        for other in ranked)
        out.append('{:>3}  {:<{w}}'.format(i, player.name, w=MAX_NAME_LENGTH) + cells)
    return '\n'.join(out) + '\n'


def print_notes(title, notes):
    if notes:
        print('\n' + title)
        for file, message in notes:
            print('  {}: {}'.format(file, message))


# ----------------------------------------------------------------------------
# One against one
# ----------------------------------------------------------------------------
def find_player(players, wanted):
    '''Find a player from their strategy name, or the start of it.'''
    exact = [p for p in players if simplify(p.name) == simplify(wanted)]
    close = exact or [p for p in players if simplify(wanted) and simplify(wanted) in simplify(p.name)]
    if len(close) == 1:
        return close[0]
    print('\n"{}" matches {} strategies. The names are:'.format(wanted, len(close) or 'no'))
    for player in sorted(players, key=lambda p: p.name.casefold()):
        print('  ' + player.name)
    return None


def home_player(players, opponent):
    '''With only an opponent named, the other player is "your" strategy: the one in strategies/.'''
    mine = [p for p in players if p.file.startswith('strategies/') and p is not opponent]
    own = [p for p in mine if Path(p.file).name.casefold() != DEMO_FILENAME] or mine
    if len(own) == 1:
        return own[0]
    print('\nThere {} in the strategies folder, so name both players, for example:'.format(
        'are {} strategies'.format(len(own)) if own else 'is no strategy'))
    print('  python run_tournament.py --versus "{}" "Other Name"'.format(opponent.name))
    return None


def play_versus(players, names, games, speed, live):
    if len(names) > 2:
        print('\n--versus takes one or two strategy names.')
        return 1
    first = find_player(players, names[0])
    second = first and (find_player(players, names[1]) if len(names) == 2 else home_player(players, first))
    if not first or not second:
        return 1
    if len(names) == 1:
        first, second = second, first       # "your" strategy goes on the left
    return play_pair(first, second, games, speed, live)


def fresh_copy(player, name=None):
    '''The same strategy again, with its own variables and a clean score sheet.'''
    module = {'__name__': 'strategy_copy', '__file__': player.file}
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(player.source, player.file, 'exec'), module)
    place_ships = module.get('place_ships')
    return Player(name or player.name, player.file, module['take_shot'],
                  place_ships if callable(place_ships) else None, player.source)


def play_pair(first, second, games, speed, live):
    '''Play a series between two strategies. A strategy may play against itself.'''
    try:
        twin_name = '{} (copy)'.format(first.name) if first is second else None
        first, second = fresh_copy(first), fresh_copy(second, twin_name)
    except Exception as error:
        print('\nCould not start the game: {}'.format(describe_error(error)))
        return 1
    pause = 1 / speed if speed > 0 else 0
    order = random.choice([0, 1])

    def show(game):
        left = game if game.players[0] is first else None
        lines = ['', '   BATTLESHIP   game {} of {}      {} {}  -  {} {}'.format(
            number, games, first.name, first.wins, second.wins, second.name), '']
        draw(lines + game_lines(game if left else Mirror(game)))
        time.sleep(pause)

    if live:
        start_screen()
    try:
        for number in range(1, games + 1):
            pair = (first, second) if (number + order) % 2 else (second, first)
            game = Game(*pair).play(show if live else None)
            if live:
                time.sleep(min(2, 1.5 * bool(pause)))
            else:
                print('Game {}: {}'.format(number, game.summary()))
    except KeyboardInterrupt:
        print('\n\nStopped.')
    finally:
        if live:
            end_screen()
    print('\n   {} won {}, {} won {}{}'.format(first.name, first.wins, second.name, second.wins,
                                             ', {} drawn'.format(first.draws) if first.draws else ''))
    for player in (first, second):
        if player.wins:
            print('   {} needed {:.1f} shots on average to win'.format(player.name, player.shots_per_win))
    print_notes('PROBLEMS DURING PLAY:', trouble([first, second]))
    return 0


def ask(keyboard, question):
    '''Ask on the real keyboard. Returns None if the user presses Ctrl+C.'''
    sys.stdin = keyboard
    try:
        return input(question).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    finally:
        sys.stdin = io.StringIO('')


def ask_number(keyboard, question, highest, default=None):
    '''Ask for a whole number from 1 to highest. Returns None to go back.'''
    while True:
        answer = ask(keyboard, question)
        if answer is None or (answer == '' and default is None):
            return None
        if answer == '' and default is not None:
            return default
        if answer.isdigit() and 1 <= int(answer) <= highest:
            return int(answer)
        print('   Please type a number from 1 to {}.'.format(highest))


def menu(keyboard, players, tournament_games, games, speed, live):
    '''The choices shown when the program is started without any options.
    Returns True to play the tournament, False to exit.'''
    # Strategies in examples/.hidden can be picked for one-v-one, but they
    # are not part of the tournament.
    hidden = HERE / 'examples' / '.hidden'
    extras = load_strategies([hidden])[0] if hidden.is_dir() else []
    taken = {simplify(p.name) for p in players}
    listed = sorted(players + [p for p in extras if simplify(p.name) not in taken],
                    key=lambda p: p.name.casefold())
    while True:
        print('\nWhat would you like to do?')
        print('  1. Play one-v-one')
        print('  2. Play an entire tournament ({} games)'.format(tournament_games))
        print('  3. Exit')
        choice = ask_number(keyboard, 'Type 1, 2 or 3 and press Enter: ', 3)
        if choice in (None, 3):
            return False
        if choice == 2:
            return True

        print('\nThe strategies:')
        for number, player in enumerate(listed, 1):
            print('  {:>2}. {}'.format(number, player.name))
        print('(Press Enter without a number to go back. A strategy can play against itself.)')
        first = ask_number(keyboard, 'Number of the first strategy: ', len(listed))
        second = first and ask_number(keyboard, 'Number of the second strategy: ', len(listed))
        how_many = second and ask_number(keyboard, 'How many games? (Enter for {}): '.format(games), 1000, games)
        if how_many:
            play_pair(listed[first - 1], listed[second - 1], how_many, speed, live)


class Mirror:
    '''The same game with the two players swapped, so a player stays on the same side of the screen.'''

    def __init__(self, game):
        self.players = game.players[::-1]
        self.fleets = game.fleets[::-1]
        self.views = game.views[::-1]
        self.shots = game.shots[::-1]
        self.hits = game.hits[::-1]
        self.last = game.last[::-1]
        self.ships_left = lambda shooter: game.ships_left(1 - shooter)


# ----------------------------------------------------------------------------
# Main program
# ----------------------------------------------------------------------------
def main():
    global GAMES_PER_PAIR
    parser = argparse.ArgumentParser(description='Run a Battleship tournament.')
    parser.add_argument('folders', nargs='*', help='folders of strategies (default: strategies and examples)')
    parser.add_argument('--no-examples', action='store_true', help='play only the strategies folder (the demo stays in as the baseline)')
    parser.add_argument('--check', action='store_true', help="check the files but don't play")
    parser.add_argument('--watch', action='store_true', help='show both boards during every game of the tournament')
    parser.add_argument('--versus', nargs='+', metavar='NAME',
                        help='watch one strategy against another, chosen by strategy name (one name = against yours)')
    parser.add_argument('--speed', type=float, default=10,
                        help='shots per second when the boards are shown (default 10, 0 = as fast as possible)')
    parser.add_argument('--games', type=int, help='how many games to play (per pair in a tournament, or in a --versus series)')
    parser.add_argument('--seconds', type=float, default=10,
                        help='roughly how long a tournament without boards should take (default 10, 0 = no pauses)')
    parser.add_argument('--yes', action='store_true', help="don't wait for Enter before starting")
    parser.add_argument('--seed', type=int, help='make the random numbers repeatable')
    parser.add_argument('--probe', help=argparse.SUPPRESS)      # used by the pre-start check
    args = parser.parse_args()
    if args.probe:
        probe(args.probe)
        return 0

    for stream in (sys.stdout, sys.stderr):     # so names with accents or emoji can be printed
        with contextlib.suppress(Exception):
            stream.reconfigure(encoding='utf-8', errors='replace')
    if args.seed is not None:
        random.seed(args.seed)
    if args.games is not None and args.games < 1:
        parser.error('--games must be at least 1')

    if args.folders:
        folders = [Path(folder).resolve() for folder in args.folders]
    elif args.no_examples:
        folders = [HERE / 'strategies']
    else:
        folders = [HERE / 'strategies', HERE / 'examples']

    print('\nChecking the strategy files...')
    keyboard, sys.stdin = sys.stdin, io.StringIO('')    # a strategy calling input() gets an error, not a wait
    players, problems, warnings = load_strategies(folders)

    print('\nBATTLESHIP TOURNAMENT')
    print('\n{} strategies ready to play:'.format(len(players)))
    for player in sorted(players, key=lambda p: p.name.casefold()):
        print('  {:<{w}}  {}'.format(player.name, player.file, w=MAX_NAME_LENGTH))
    print_notes('WARNINGS (these will still play):', warnings)
    print_notes('PROBLEMS (these will NOT play until they are fixed):', problems)

    if args.check:
        return 1 if problems else 0
    live = sys.stdout.isatty()
    if args.versus:
        return play_versus(players, args.versus, args.games or 1, args.speed, live)
    if len(players) < 2:
        print('\nAt least two strategies are needed to play.')
        return 1

    if args.games:
        GAMES_PER_PAIR = args.games
    schedule = [pair if game % 2 == 0 else pair[::-1]       # take turns to shoot first
                for pair in itertools.combinations(players, 2) for game in range(GAMES_PER_PAIR)]
    random.shuffle(schedule)
    results_path = HERE / RESULTS_FILENAME
    if live and len(sys.argv) == 1:
        # Started without any options: offer the choices.
        if not menu(keyboard, players, len(schedule), 1, args.speed, live):
            return 0
    elif live and not args.yes:
        if ask(keyboard, '\nPress Enter to play {} games (or Ctrl+C to stop) '.format(len(schedule))) is None:
            return 1
    if live:
        start_screen()
    else:
        print()

    watching = live and args.watch
    shot_pause = 1 / args.speed if args.speed > 0 else 0
    game_pause = 0 if watching else args.seconds / len(schedule)
    done = 0
    latest = '-'
    previous_ranks = None
    last_save = 0
    status = 'FINAL RESULTS'

    def show(game):
        lines = progress_lines(done + 1, len(schedule), latest) + game_lines(game) + ['']
        height = shutil.get_terminal_size((100, 40)).lines
        draw(lines + leaderboard_lines(players, previous_ranks, limit=max(3, height - len(lines) - 4)))
        time.sleep(shot_pause)

    try:
        for player1, player2 in schedule:
            current = '{} vs {}'.format(player1.file, player2.file)
            game = Game(player1, player2).play(show if watching else None)
            done += 1
            latest = game.summary()
            if watching:
                time.sleep(min(1, 5 * shot_pause))
            elif live:
                lines = progress_lines(done, len(schedule), latest)
                height = shutil.get_terminal_size((100, 40)).lines
                draw(lines + leaderboard_lines(players, previous_ranks, limit=max(3, height - len(lines) - 4)))
            else:
                print('Game {} of {}: {}'.format(done, len(schedule), latest))
            previous_ranks = {p: rank for rank, p in enumerate(standings(players), 1)}
            if time.time() - last_save > 1:
                results_path.write_text(build_report(players, done, len(schedule), problems, warnings,
                                                     'IN PROGRESS'), encoding='utf-8')
                last_save = time.time()
            time.sleep(game_pause)
    except KeyboardInterrupt:
        status = 'STOPPED EARLY'
        print('\n\nStopped during the game {}.'.format(current))
        print('If it was stuck, one of those two strategies probably has a loop that never ends.')
    finally:
        if live:
            end_screen()

    results_path.write_text(build_report(players, done, len(schedule), problems, warnings, status), encoding='utf-8')
    if live and status == 'FINAL RESULTS':
        sys.stdout.write('\x1b[2J\x1b[H')
    print('\n   {} - {} games played\n'.format(status, done))
    print('\n'.join(leaderboard_lines(players)))
    if status == 'FINAL RESULTS':
        print('\n'.join(prize_lines(players)))
    print_notes('WASTED SHOTS AND BAD SHIP PLACEMENTS:', trouble(players))
    print_notes('DID NOT PLAY:', problems)
    print('\nFull details are in {}'.format(results_path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
