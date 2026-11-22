# =============================================================================
#  BATTLESHIP - YOUR STRATEGY FILE
# =============================================================================
#
#  To enter the tournament:
#
#    1. Change strategy_name below to your name or your team's name.
#    2. Replace the code inside take_shot() with your own strategy.
#    3. Rename this file to anything else ending in .py
#       (for example:  maria_and_sam.py).
#
#  You must do BOTH 1 and 3. The tournament will refuse a file that is still
#  called demo_strategy.py with a new name inside it, or a renamed file that
#  still says 'Demo Strategy'.
#
#  To watch your strategy play, put your file in the "strategies" folder and run
#       python run_tournament.py --versus rando
#  See README.md for the full rules.
# =============================================================================

import random

strategy_name = 'Demo Strategy'


def take_shot(board, ships_left):
    '''Choose where to shoot next. Must return (row, column).

    This function is called every time it is your turn. You are given:

    board       what you know so far about the board you are shooting at.
                board[row][column] is one of these letters:
                    '.'   you have not shot here yet
                    'M'   you shot here and missed
                    'H'   you shot here and hit a ship that is still afloat
                    'S'   you shot here, and that ship has now been sunk
                Rows and columns are both numbered 0 to 9.
                board[0][0] is the top left corner, board[0][9] the top right.

    ships_left  the lengths of the enemy ships you have not sunk yet.
                At the start it is [5, 4, 3, 3, 2].

    Shooting off the board, or at a square you have already shot at, wastes
    your turn.
    '''

    # ----- The demo strategy: shoot at a random square you haven't tried. -----
    # Replace everything from here to the end of the function with your idea.
    #
    # This is a weak strategy for two reasons, and fixing each one is a good
    # place to start:
    #
    #   1. SEARCHING. Random shots waste a lot of turns. The smallest ship is
    #      2 squares long, so do you really need to shoot at every square to
    #      find it? Is there a pattern that finds ships faster? (Look in the
    #      "examples" folder for two different patterns.)
    #
    #   2. AFTER A HIT. This code does nothing special when it hits a ship: it
    #      just carries on shooting at random! If board[row][column] is 'H',
    #      the rest of that ship must be right next to it. Where should your
    #      next shot go? And once you have two hits in a line, where then?

    not_tried_yet = []
    for row in range(10):
        for column in range(10):
            if board[row][column] == '.':
                not_tried_yet.append((row, column))

    return random.choice(not_tried_yet)


# -----------------------------------------------------------------------------
# OPTIONAL: choosing where your own ships go.
#
# If you do nothing, your ships are placed at random each game, which is a
# perfectly good choice. To place them yourself, remove the # signs from the
# function below and change it.
#
# You are given ship_lengths, which is [5, 4, 3, 3, 2]. Return a list with one
# (row, column, direction) for each ship, in that order. (row, column) is the
# ship's top or left end, and direction is 'across' or 'down'. Ships must stay
# on the board and must not overlap. If your answer breaks those rules, your
# ships are placed at random instead.
# -----------------------------------------------------------------------------
# def place_ships(ship_lengths):
#     return [(0, 0, 'across'),      # the ship of length 5, along the top row
#             (2, 0, 'across'),      # the ship of length 4
#             (4, 0, 'down'),        # the first ship of length 3
#             (4, 2, 'down'),        # the second ship of length 3
#             (9, 8, 'across')]      # the ship of length 2


# -----------------------------------------------------------------------------
# You don't need to change anything below. If you run THIS file by itself, it
# shows what your take_shot() does in a couple of made-up situations - a quick
# way to see whether your code works before you play a whole game.
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    empty = [['.'] * 10 for row in range(10)]
    one_hit = [['.'] * 10 for row in range(10)]
    one_hit[4][5] = 'H'
    one_hit[4][4] = 'M'
    print('Testing', strategy_name)
    for description, test_board in [('On an empty board', empty),
                                    ('After a hit at (4, 5) and a miss at (4, 4)', one_hit)]:
        shot = take_shot([row[:] for row in test_board], [5, 4, 3, 3, 2])
        print('  {}, my shot is {!r}'.format(description, shot))
        if not (isinstance(shot, tuple) and len(shot) == 2):
            print('    PROBLEM: take_shot() has to return (row, column).')
        elif not (0 <= shot[0] <= 9 and 0 <= shot[1] <= 9):
            print('    PROBLEM: that is off the board. Rows and columns go from 0 to 9.')
        elif test_board[shot[0]][shot[1]] != '.':
            print('    PROBLEM: that square has already been shot at.')
