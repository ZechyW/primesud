#  Extracted from HP tape image 16-Nov-2003 by Pete Turnbull

# ****  HP BASIC Program Library  ******************************
#
#       sttr1: Star Trek
#
#       36243  Rev B  --  10/73
#
# ****  Contributed Program  ***********************************
# *****************************************************************
# ***                                                           ***
# ***     Star Trek: by Mike Mayfield, Centerline Engineering   ***
# ***                                                           ***
# ***        Total Interaction Game - Orig. 20 Oct 1972
# ***                                                           ***
# *****************************************************************
#
# Converted to python by Mike Markowski, mike.ab3ap@gmail.com
# Sep 2024
#
# Some big changes involved splitting the monolithic code into subroutines
# and replaced some slightly cumbersome movement logic with simpler
# trigonometry.  I also made some small changes: replaced short range scan
# strings with 2D array, modified computer range/bearing output, split off
# computer calculator to its own library coputer menu item, and added an 'e'
# command to end game.  I also changed strings to mixed case.  Nostalgia is
# great, but all upper case...not so much.  :-)

from math import atan2, cos, pi, sin, sqrt
from urandom import random, randint
from tml import tml
import hpprime as h
import sys

def adrift():
    tr.print('The Enterprise is dead in space.  If you')
    tr.print('survive all impending attack you will be')
    tr.print('demoted to the rank of Private')
    while True:
        if k3 <= 0:
            lose(True)
        klingonAttack()

def computer():
    global d, q1, q2, z

    if d[7] < 0:
        tr.print('Computer disabled')
        return
    while True:
        a = tr.input('Computer active and awaiting command: ',
            alpha=False, shift=False)
        a = a.strip()
        if a != '':
            a = a[0]
        if a in ['0', '1', '2', '3']:
            break
        tr.print('Functions available from computer')
        tr.print('   0 = Cumulative galactic record')
        tr.print('   1 = Status report')
        tr.print('   2 = Photon torpedo data')
        tr.print('   3 = Direction calculator')

    if a == '0':
        tr.print('Computer record of galaxy for quadrant %d,%d' % (q1+1, q2+1))
        tr.print('     1     2     3     4     5     6     7     8')
        tr.print('   ----- ----- ----- ----- ----- ----- ----- -----')
        for i in range(8):
            tr.print('%d   %3d   %3d   %3d   %3d   %3d   %3d   %3d   %3d'
                % (i+1,z[i][0],z[i][1],z[i][2],z[i][3],z[i][4],z[i][5],
                z[i][6],z[i][7]))
            tr.print('   ----- ----- ----- ----- ----- ----- ----- -----')
    elif a == '1':
        tr.print('\n   Status Report\n')
        tr.print('Number of Klingons left = %d' % k9)
        tr.print('Number of Stardates left = %d' % (t0+t9-t))
        tr.print('Number of Starbases left = %d' % b9)
        damageControl()
    elif a == '2':
        for i in range(3):
            if k[i][2] <= 0:
                continue
            rng, theta = vec(s2, s1, k[i][1], k[i][0])
            tr.print(' Range %.1f, bearing %.1f' % (rng, theta))
    else:
        tr.print('You are at quadrant (%d,%d) sector (%d,%d)'
            % (q1+1, q2+1, s1+1, s2+1))
        line = tr.input('Ship\'s & target\'s coordinates are: ',
            alpha=False, shift=False)
        try:
            line = line.replace(',', ' ').split()
            line = map(int, line)
            y0, x0, y1, x1 = line
        except ValueError:
            return
        rng, theta = vec(x0, y0, x1, y1)
        # Original output by Mike Mayfield.
        # tr.print('Direction = %.2f' % theta)
        # tr.print('Distance = %.2f' % rng)
        tr.print(' Range %.1f, bearing %.1f' % (rng, theta))

def course():
    global c, d, e, g, k3, s, s1, s2, q1, q2, t, t0, t9

    while True:
        c1 = inputSafe(float, 'Course (1-9): ')
        if c1 == 0:
            return
        if not (1 <= c1 < 9):
            continue
        w1 = inputSafe(float, 'Warp factor (0-8): ')
        if not (0 <= w1 <= 8):
            continue
        if d[0] >= 0 or w1 <= 0.2:
            break
        tr.print('Warp engines are damaged, maximum speed = warp .2')

    if k3 > 0:
        klingonAttack()
        if s <= 0:
            lose()
    elif e <= 0:
        if s < 1:
            adrift()
        tr.print('You have %d units of energy' % e)
        tr.print('Suggest you get some from your shields which have %d units left'
            % s)
        return

    for i in range(8):
        if d[i] >= 0:
            continue
        d[i] += 1
    if random() < 0.2:
        r1 = randint(0,7)
        if random() < 0.5:
            d[r1] -= random()*5 + 1
            tr.print('\nDamage control report: %s damaged\n' % ds[r1])
        else:
            d[r1] += random()*5 + 1
            tr.print('\nDamage control report: %s state of repair improved\n'
                % ds[r1])

    n = int(w1*8)
    q[s1][s2] = '   '
    x = s1
    y = s2
    x1 = -sin((c1 - 1)*pi/4) # Unit vector, course c1 is multiple of 45 deg.
    x2 =  cos((c1 - 1)*pi/4)
    blocked = False
    leaving = False
    for _ in range(n): # Check for objects blocking way.
        x += x1
        y += x2
        z1 = round(x) # Nearest sector.
        z2 = round(y)
        if not (0 <= z1 <= 7 and 0 <= z2 <= 7): # Left quadrant.
            leaving = True
            break
        if q[z1][z2] == '   ': # Traveling in open space.
            continue
        blocked = True
        tr.print(' Warp engines shutdown at sector %d,%d due to bad navigation'
            % (z1+1, z2+1))
        x -= x1
        y -= x2
        s1,s2 = int(x),int(y)
        break

    if not blocked: # Inter-quadrant travel.
        x = q1 + s1/8 + w1*x1 # Destination quadrant, real.
        y = q2 + s2/8 + w1*x2
        if    x <  0: x = s1 = 0
        elif  x >= 8: x = s1 = 7
        else: s1 = int((8*(x - int(x)))%8) # Sector, integer.
        if    y <  0: y = s2 = 0
        elif  y >= 8: y = s2 = 7
        else: s2 = int((8*(y - int(y)))%8)
        z1 = int(x) # Quadrant, integer.
        z2 = int(y)
        if (q1,q2) != (z1,z2):
            q1,q2 = z1,z2
            mkQuadrant()

    q[s1][s2] = '<*>' # Enterprise arrival sector.
    e += -n + 5
    if w1 >= 1:
        t += 1
    if t > t0+t9:
        lose(True)

def damageControl():
    if d[5] < 0:
        tr.print('Damage control report is not available')
        return
    tr.print('\nDevice        State of Repair')
    for r1 in range(8):
        tr.print('%-14s%d' % (ds[r1], d[r1]))
    tr.print('')

def dist(x0, y0, x1, y1):
    return sqrt((x0 - x1)**2 + (y0 - y1)**2)

def emptySector(q):
    while True:
        r1 = randint(0,7)
        r2 = randint(0,7)
        if q[r1][r2] == '   ':
            return r1,r2

def inputSafe(dtype, prompt):
    '''Keep trying for correct input until user does it right!  This prevents
    the game from dying on incorrect type of response, e.g., accidentally
    entering a text command when a number is expected.
    '''

    while True:
        try:
            ans = dtype(tr.input(prompt, alpha=False))
            return ans
        except ValueError:
            tr.print(ans)
            pass

def instructions():
    tr.print('''     Instructions:
<*> = Enterprise
+++ = Klingon
>!< = Starbase
 *  = Star
Command 0 = Warp Engine Control
  'Course' is in a circular numerical          4  3  2
  vector arrangement as shown.                  \ ^ /
  Interger and real values may be                \^/
  used.  Therefore course 1.5 is              5 ----- 1
  half way between 1 and 2.                      /^\\
                                                / ^ \\
  A vector of 9 is undefined, but              6  7  8
  values may approach 9.
                                               course
  One 'warp factor' is the size of
  one quadrant.  Therefore to get
  from quadrant 6,5 to 5,5 you would
  use course 3, warp factor 1
Command 1 = Short Range Sensor Scan
  Prints the quadrant you are currently in, including
  stars, Klingons, starbases, and the Enterprise; along
  with other pertinate information.
Command 2 = Long Range Sensor Scan
  Shows conditions in space for one quadrant on each side
  of the enterprise in the middle of the scan.  The scan
  is coded in the form XXX, where the units digit is the
  number of stars, the tens digit is the number of star-
  bases, the hundreds digit is the number of Klingons.
Command 3 = Phaser Control
  Allows you to destroy the Klingons by hitting him with
  suitably large numbers of energy units to deplete his 
  shield power.  Keep in mind that when you shoot at
  him, he gonna do it to you too.
Command 4 = Photon Torpedo Control
  Course is the same as used in warp engine control
  if you hit the Klingon, he is destroyed and cannot fire
  back at you.  If you miss, he will shoot his phasers at
  you.
   Note: The Library Computer (command 7) has an option
   to compute torpedo trajectory for you (option 2).
Command 5 = Shield Control
  Defines number of energy units to be assigned to shields
  energy is taken from total ship's energy.
Command 6 = Damage Control Report
  Gives state of repairs of all devices.  A state of repair
  less than zero shows that that device is temporaraly
  damaged.
Command 7 = Library Computer
  The Library Computer contains three options:
    Option 0 = Cumulative Galactic Record
     shows computer memory of the results of all previous
     long range sensor scans
    Option 1 = Status Report
     Shows number of Klingons, stardates and starbases
     left.
    Option 2 = Photon Torpedo Data
     gives trajectory and distance between the enterprise
     and all Klingons in your quadrant
''')

def klingonAttack():
    global cs, k, s, s1, s2

    if cs == 'Docked':
        tr.print('Star base shields protect the enterprise')
        return
    if k3 <= 0: 
        return
    for i in range(3):
        if k[i][2] <= 0:
            continue
        far = dist(k[i][0], k[i][1], s1, s2)
        h = (k[i][2]/far)*(2*random())
        s = max(0, s-h)
        tr.print('%4d unit hit on Enterprise at sector %d,%d   (%4d left)'
            % (h, k[i][0]+1, k[i][1]+1, s))
        if s <= 0:
            lose()

def lose(tooLong=False):
    global k9, t

    if tooLong:
        tr.print('\nIt is stardate %d' % t)
    else:
        tr.print('\nThe Enterprise has been destroyed.')
        tr.print('The Federation will be conquered')
    tr.print('There are still %d Klingon battle cruisers' % k9)
    tr.input('\nPress return to exit')
    sys.exit(0)

def lrScan():
    global g, q1, q2

    if d[2] < 0:
        tr.print('Long range sensors are inoperable')
        return
    tr.print('Long range sensor scan for quadrant %d,%d' % (q1+1,q2+1))
    tr.print('-------------------')
    for i in range(q1-1, q1+2):
        n = [0,0,0]
        for j in range(q2-1, q2+2):
            if not (0 <= i <= 7 and 0 <= j <= 7):
                continue
            n[j-q2+1] = g[i][j]
            if d[7] < 0: # Computer unavailable for storage.
                continue
            z[i][j] = g[i][j]
        tr.print(': %3d : %3d : %3d :' % (n[0],n[1],n[2]))
        tr.print('-------------------')

def mkGalaxy():
    global b3, b9, k3, k7, k9, s3, g, z

    while True: # Keep trying till >= 1 star base and >= 1 Klingon exist.
        for i in range(8):
            for j in range(8):
                r1 = random()
                if r1 > 0.98:
                    k3 = 3
                    k9 += 3
                elif r1 > 0.95:
                    k3 = 2
                    k9 += 2
                elif r1 > 0.8:
                    k3 = 1
                    k9 += 1
                else:
                    k3 = 0
                r1 = random()
                if r1 > 0.96:
                    b3 = 1
                    b9 += 1
                else:
                    b3 = 0
                s3 = randint(1,8)
                g[i][j] = k3*100 + b3*10 + s3
                z[i][j] = 0
        k7 = k9
        if b9 > 0 and k9 > 0:
            break
    tr.print('You must destroy %d Klingons in %d Stardates with %d Starbases\n'
        % (k9, t9, b9))

def mkQuadrant():
    global b3, k3, s3, b9, k, k9, q, q1, q2, s1, s2, s9, t9

    if not (0 <= q1 <= 7 and 0 <= q2 <= 7):
        tr.print('Out of galaxy.  This shouldn\'t happen.')
        return

    k3,b3,s3 = list(map(int,list('%03d' % g[q1][q2])))
    if k3 != 0 and s <= 200:
        tr.print('Combat Area      Condition Red')
        tr.print('   Shields Dangerously Low')

    # Clear old Klingon info.
    k = [[0,0,0],
         [0,0,0],
         [0,0,0]]
    q = []
    for _ in range(8):
        row = []
        for _ in range(8):
            row.append('   ')
        q.append(row)
    q[s1][s2] = '<*>'          # Place Enterprise.
    for i in range(k3):
        r1,r2 = emptySector(q)
        q[r1][r2] = '+++'      # Place Klingon.
        k[i][0] = r1
        k[i][1] = r2
        k[i][2] = s9
    for i in range(b3):
        r1,r2 = emptySector(q)
        q[r1][r2] = '>!<'      # Place star base.
    for i in range(s3):
        r1,r2 = emptySector(q)
        q[r1][r2] = ' * '      # Place star.

def phasers():
    global b3, d, e, g, k, k3, k9, q, s3

    if k3 <= 0:
        tr.print('Short range sensors report no klingons in this quadrant')
        return
    if d[3] < 0:
        tr.print('Phaser control is disabled')
        return
    while True:
        if d[7] < 0:
            tr.print(' Computer failure hampers accuracy')
        tr.print('Phasers locked on target.  Energy available=%d' % e)
        x = inputSafe(int, 'Number of units to fire: ')
        if x <= 0:
            return
        if e-x < 0:
            continue
        break
    e -= x
    klingonAttack()
    if d[7] < 0:
        x *= random()
    for i in range(3):
        if k[i][2] <= 0: # No Klingon here.
            continue
        far = dist(k[i][0], k[i][1], s1, s2)
        h = (x/k3/far)*(2*random())
        k[i][2] = max(0, k[i][2]-h)
        tr.print('%4d unit hit on Klingon at sector %d,%d   (%3d left)'
            % (h, 1+k[i][0], 1+k[i][1], k[i][2]))
        if k[i][2] <= 0:
            tr.print('Klingon at sector %d,%d destroyed ****'
                % (1+k[i][0],1+k[i][1]))
            k3 -= 1
            k9 -= 1
            q[k[i][0]][k[i][1]] = '   '
            g[q1][q2] = k3*100 + b3*10 + s3
            if k9 <= 0:
                win()
    if e < 0:
        lose()

def shields():
    global d, e, s

    if d[6] < 0:
        tr.print('Shield control is non-operational')
        return
    while True:
        x = inputSafe(int,
            'Energy available = %d   Number of units to shields: ' % (e+s))
        if x <= 0:
            return
        if e+s-x >= 0:
            break
    e += s - x
    s = x

def srLine(line, p0, p1):
    tr.print('in:  "%s"' % line)
    spaced = ''
    for i in range((p1-p0)//3):
        l0 = 3*i + p0
        spaced += ' %3s' % line[l0:l0+3]
    tr.print('out: "%s"' % spaced)
    return spaced

def srScan():
    global cs, d, e, g, p, q, q1, q2, s, z

    d0 = 0
    # Look for star base in adjacent sectors.
    for i in range(s1-1, s1+2):
        for j in range(s2-1, s2+2):
            if not (0 <= i <= 7 and 0 <= j <= 7):
                continue
            if q[i][j] == '>!<':
                d0 = 1
                i = j = 10 # Break from loops.
    if d0 == 1: # Adjacent to star base.
        cs = 'Docked'
        e = 3000
        p = 10
        tr.print('Shields dropped for docking purposes')
        s = 0
    elif k3 > 0: # Klingons here.
        cs = 'Red'
    elif e < e0/10: # Enterprise energy level is low.
        cs = 'Yellow'
    else: # Beam down for shore leave!
        cs = 'Green'

    if d[1] < 0:
        tr.print('\n*** Short range sensors are out ***\n')
        return
    tr.print('---------------------------------')
    for i in range(8):
        for j in range(8):
            tr.print(' %3s' % q[i][j], end='')
        if   i == 0: tr.print('')
        elif i == 1: tr.print('        Stardate        %5d' % t)
        elif i == 2: tr.print('        Condition        %-6s' % cs)
        elif i == 3: tr.print('        Quadrant         %d,%d' % (q1+1,q2+1))
        elif i == 4: tr.print('        Sector           %d,%d' % (s1+1,s2+1))
        elif i == 5: tr.print('        Energy           %d' % e)
        elif i == 6: tr.print('        Photon Torpedoes %d' % p)
        elif i == 7: tr.print('        Shields          %d' % s)
    tr.print('---------------------------------')
    z[q1][q2] = g[q1][q2]

def torpedoes():
    global b3, c, d, g, k, k3, k9, p, q, q1, q2, s1, s2, s3

    if d[4] < 0:
        tr.print('Photon tubes are not operational')
        return
    if p <= 0:
        tr.print('All photon torpedoes expended')
        return
    while True:
        c1 = inputSafe(float, 'Torpedo course (1-9): ')
        if c1 == 0:
            return
        if 1 <= c1 < 9:
            break
    x1 = -sin((c1 - 1)*pi/4)
    x2 = cos((c1 - 1)*pi/4) # Unit vector, course c1 is multiple of 45 deg.
    x,y = s1,s2             # Start at current sector.
    p -= 1                  # Use 1 photon torpedo.
    tr.print('Torpedo track:')
    while True:
        x += x1
        y += x2
        z1 = int(x + 0.5)
        z2 = int(y + 0.5)   # Nearest sector.
        if not (0 <= z1 <= 7 and 0 <= z2 <= 7): # Torpedo left quadrant.
            tr.print('Torpedo missed')
            klingonAttack()
            return
        tr.print('%15s%d,%d' % (' ', x+1, y+1))
        if q[z1][z2] != '   ': # Torpedo hit something.
            break
    if q[z1][z2] == '+++':  # Hit Klingon.
        tr.print('*** Klingon destroyed ***')
        k3 -= 1
        k9 -= 1
        if k9 <= 0:
            win()
        for i in range(3):
            if (z1,z2) == (k[i][0],k[i][1]):
                break
        k[i][2] = 0
        q[z1][z2] = '   '
        g[q1][q2] = k3*100 + b3*10 + s3
    elif q[z1][z2] == ' * ': # Hit star.
        tr.print('You can\'t destroy stars silly')
        tr.print('Torpedo missed')
    elif q[z1][z2] == '>!<': # Hit star base.
        tr.print('*** Star base destroyed ***  .......Congratulations')
        b3 -= 1
        q[z1][z2] = '   '
        g[q1][q2] = k3*100 + b3*10 + s3
    klingonAttack()

def vec(ex, ey, tx, ty):
    theta = atan2(-(ty-ey), tx-ex)/(pi/4)
    if theta <= 0:
        theta += 8
    theta = theta%8 + 1
    dist = sqrt((tx-ex)**2 + (ty-ey)**2)
    return dist, theta

def win():
    global k7, t, t0, t7

    tr.print('\nThe last Klingon battle cruiser in the galaxy has been destroyed')
    tr.print('The Federation has been saved !!!\n')
    tr.print('Your efficiency rating = %d' % round((k7/(t-t0))*1000))
    t1 = h.eval('TICKS')/1000 # Internal clock in msec.
    tr.print('Your actual time of mission = %d minutes' % round((t1-t7)/60))
    tr.input('\nPress return to exit')
    sys.exit(0)

def sttr1():
    tr.clear()
    tr.print('                          Star Trek\n')
    tr.print('           by Mike Mayfield, Centerline Engineering')
    tr.print('          Total Interaction Game - Orig. 20 Oct 1972\n')
#   a = tr.input('Do you want instructions (they\'re long!)? ').strip().lower()
#   if a == '':
#       a = 'n'
#   if a[0] == 'y':
#       instructions()
    tr.print('')

    # *****  Program starts here *****
    mkGalaxy()
    mkQuadrant()
    srScan()
    while True:
        a = tr.input('Command: ', alpha=False, shift=False).strip()
        if a != '':
            a = a.lower()[0]
        if a == '0':
            course()
            srScan()
        elif a == '1':
            srScan()
        elif a == '2':
            lrScan()
        elif a == '3':
            phasers()
        elif a == '4':
            torpedoes()
        elif a == '5':
            shields()
        elif a == '6':
            damageControl()
        elif a == '7':
            computer()
        elif a == 'e':
            lose(True)
            break
        else:
            tr.print('')
            tr.print('   0 = Set course')
            tr.print('   1 = Short range sensor scan')
            tr.print('   2 = Long range sensor scan')
            tr.print('   3 = Fire phasers')
            tr.print('   4 = Fire photon torpedoes')
            tr.print('   5 = Shield control')
            tr.print('   6 = Damage control report')
            tr.print('   7 = Call on library computer')
            tr.print('   e = End game')
            tr.print('')

# The many globals of STTR1!
g = [[0,0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0,0]]
z = [[0,0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0,0]]
k = [[0,0,0],
     [0,0,0],
     [0,0,0]]
n = [0,0,0]
d = [0,0,0,0,0,0,0,0]

t0 = t = randint(20,39)*100
t9 = 30
d0 = 0
e0 = e = 3000
p0 = p = 10
s9 = 200
s = 0
q1 = randint(0,7)
q2 = randint(0,7)
s1 = randint(0,7)
s2 = randint(0,7)
t7 = h.eval('TICKS')/1000 # Internal clock in msec.
ds = ['Warp Engines', 'S.R. Sensors', 'L.R. Sensors', 'Phaser Cntrl',
    'Photon Tubes', 'Damage Cntrl', 'Shield Cntrl', 'Computer']
b9 = k9 = 0
tr = tml(dark_mode = True, tab_size = 8, bg_color = 0x3000)

sttr1()
