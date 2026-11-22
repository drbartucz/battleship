# Mr. Bartucz's own strategy, which won a previous tournament. It is not an
# entry in this one and it can't win a duck.
#
# You found it before the reveal. Well done. Now write something better.

strategy_name = 'Mr. Bartucz'

# HOW IT WORKS
#
# It builds a "heat map": a number for every square that says how likely it
# is that a ship is there. Then it shoots at the hottest square.
#
# To build the heat map it takes every ship that is still afloat and tries
# it in every position on the board, across and down. A position is possible
# if it doesn't cover a miss or a ship that has already been sunk. Every
# untried square in a possible position gets hotter.
#
#   SEARCHING   With no hits on the board, a square is hot if lots of ships
#               could still be lying across it. Squares boxed in by misses
#               go cold, because nothing fits there any more.
#
#   AFTER A HIT Only positions that cover a hit are counted, so every shot
#               goes next to a hit. A position that covers two hits counts
#               for much more than one that covers a single hit, so once it
#               has two hits in a line it keeps going along that line.

# How much more a position counts for each hit it covers.
HIT_BONUS = 100


def positions(length, size):
    '''Every way a ship of this length can lie on the board, as lists of squares.'''
    for row in range(size):
        for column in range(size - length + 1):
            yield [(row, column + i) for i in range(length)]        # across
    for row in range(size - length + 1):
        for column in range(size):
            yield [(row + i, column) for i in range(length)]        # down


def heat_map(board, ships_left, chasing):
    size = len(board)
    heat = [[0] * size for row in range(size)]
    for length in ships_left:
        for squares in positions(length, size):
            marks = [board[row][column] for row, column in squares]
            if 'M' in marks or 'S' in marks:
                continue                    # the ship can't be here
            hits = marks.count('H')
            if chasing and hits == 0:
                continue                    # we only care about ships we have hit
            for row, column in squares:
                if board[row][column] == '.':
                    heat[row][column] += HIT_BONUS ** hits
    return heat


def take_shot(board, ships_left):
    import random

    chasing = any('H' in row for row in board)
    heat = heat_map(board, ships_left, chasing)
    hottest = max(max(row) for row in heat)
    if hottest == 0:
        # Nothing fits next to the hits (it should never happen): just search.
        heat = heat_map(board, ships_left, False)
        hottest = max(max(row) for row in heat)

    untried = [(row, column)
               for row in range(len(board)) for column in range(len(board))
               if board[row][column] == '.']
    best = [(row, column) for row, column in untried if heat[row][column] == hottest]
    return random.choice(best or untried)
