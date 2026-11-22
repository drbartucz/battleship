# An example strategy, and the toughest of the four. How it works is a secret.
# You are welcome to try to read it. Good luck.

import random as _

strategy_name = 'secret'

take_shot = lambda O, o, l=range(10), Il=chr(0x2e), lI=chr(0o110): (lambda I: _.choice([(O0, o0) for (O0, o0) in {(
    I1 + l1 % 2 * (2 - l1), l1_ + -~l1 % 2 * (1 - l1)) for I1 in l for l1_ in l if O[I1][l1_] == lI for l1 in l[:4]} if (
    O0, o0) in I] or I))([(lI, Il) for lI in l for Il in l if O[lI][Il] == Il_(Il, lI, O) or O[lI][Il] == chr(46)])
Il_ = lambda *_: _[2][_[1]][_[0]] if _[2][_[1]][_[0]] < chr(0x2f) else None
