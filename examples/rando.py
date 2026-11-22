# An example strategy. Read it for ideas, but write your own in the
# "strategies" folder (start from strategies/demo_strategy.py).

import random

strategy_name = 'rando'

# Shoots at a random square it hasn't tried yet. It never changes what it does,
# even after a hit.


def take_shot(board, ships_left):
    not_tried_yet = []
    for row in range(10):
        for column in range(10):
            if board[row][column] == '.':
                not_tried_yet.append((row, column))

    return random.choice(not_tried_yet)
