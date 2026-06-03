# JezzBall 1.23
# by Piotr Kowalewski (komame)
# March-May 2025

from hpprime import dimgrob, line, fillrect, blit, strblit2, keyboard, mouse, eval as ppleval
from urandom import randint, choice
from uio import FileIO
import math


class Ball:
    """
    Represents a bouncing ball in the game.
    Each ball has position, velocity, region, and rendering properties.
    """
    def __init__(self, x, y, vx, vy, region_id, size=7):
        self.x = x          # Float x-coordinate
        self.y = y          # Float y-coordinate
        self.ix = int(self.x + 0.5)  # Integer x-coordinate (rounded)
        self.iy = int(self.y + 0.5)  # Integer y-coordinate (rounded)
        self.vx = vx        # x-velocity
        self.vy = vy        # y-velocity
        self.region_id = region_id  # ID of the region the ball is in
        self.size = size    # Size of the ball (diameter)

    def update_position(self):
        """Update the ball position based on its velocity."""
        self.x += self.vx
        self.y += self.vy
        self.ix = int(self.x + 0.5)
        self.iy = int(self.y + 0.5)

    def render(self):
        """Draw the ball on the screen."""
        blit(1, self.ix, self.iy, 4)  # Blit ball sprite to the screen

    def clear(self):
        """Erase the ball from the screen."""
        if self.ix is None or self.iy is None:
            return
        strblit2(1, self.ix, self.iy, 7, 7, 2, self.ix, self.iy, 7, 7)


class Region:
    """
    Represents a rectangular region in the game.
    Regions can contain balls and be split by splitters.
    """
    def __init__(self, id, rect):
        self.id = id
        self.rect = rect  # [x, y, w, h]

    def contains_point(self, x, y):
        """Check if the region contains the given point."""
        rx, ry, rw, rh = self.rect
        return rx <= x < rx + rw and ry <= y < ry + rh


class Splitter:
    """
    Represents a splitter (line) that divides regions.
    Can be horizontal or vertical and expands when activated.
    """
    def __init__(self, x, y, orientation, speed):
        self.x = x  # Center x-coordinate
        self.y = y  # Center y-coordinate
        self.orientation = orientation  # 'h' for horizontal, 'v' for vertical
        self.active = False  # Whether the splitter is currently extending
        self.speed = speed   # Speed of extension
        self.extension = 0   # Current extension length
        self.region_id = None  # ID of the region being split
        self.max_ext = 0      # Maximum extension possible

    def move(self, dx, dy, min_x=11, max_x=248, min_y=11, max_y=167):
        """Move the splitter by the given deltas, constrained by boundaries."""
        self.x = max(min_x, min(max_x, self.x + dx))
        self.y = max(min_y, min(max_y, self.y + dy))

    def toggle_orientation(self):
        """Switch between horizontal and vertical orientation."""
        self.orientation = 'h' if self.orientation == 'v' else 'v'

    def render_waiting(self, frame):
        """Draw the splitter in waiting state (not active)."""
        if not self.active:
            if self.orientation == 'h':
                strblit2(1, self.x - 7, self.y - 2, 15, 5, 6, 10, (5 if frame % 20 < 10 else 0), 15, 5)
            else:
                strblit2(1, self.x - 2, self.y - 7, 5, 15, 6, (5 if frame % 20 < 10 else 0), 0, 5, 15)

    def render_active(self):
        """Draw the splitter in active state (extending)."""
        sx, sy, sw, sh = self.get_rect()
        fillrect(1, sx, sy, sw, sh, 0xFF3F00, 0xFF3F00)

    def clear(self):
        """Clear the splitter from the screen."""
        if not self.active:
            if self.orientation == 'h':
                strblit2(1, self.x - 7, self.y - 2, 15, 5, 2, self.x - 7, self.y - 2, 15, 5)
            else:
                strblit2(1, self.x - 2, self.y - 7, 5, 15, 2, self.x - 2, self.y - 7, 5, 15)

    def render_closed(self):
        """Draw the splitter in closed state (fully extended)."""
        sx, sy, sw, sh = self.get_rect()
        # Fill with darker gray color
        fillrect(2, sx, sy, sw, sh, 0x2F2F2F, 0x2F2F2F)
        fillrect(1, sx, sy, sw, sh, 0x2F2F2F, 0x2F2F2F)
        return sw * sh  # Return area of the splitter

    def destroy(self):
        """Remove the splitter from the screen."""
        sx, sy, sw, sh = self.get_rect()
        strblit2(1, sx, sy, sw, sh, 2, sx, sy, sw, sh)

    def launch(self, region):
        """Activate the splitter to start extending in the given region."""
        self.active = True
        self.extension = 0
        self.region_id = region.id
        self.region_rect = region.rect
        # Calculate maximum possible extension
        if self.orientation == 'h':
            self.max_ext = max(self.x - self.region_rect[0], self.region_rect[0] + self.region_rect[2] - self.x)
        else:
            self.max_ext = max(self.y - self.region_rect[1], self.region_rect[1] + self.region_rect[3] - self.y)

    def update(self):
        """Update the splitter's extension and return whether it's fully extended."""
        if not self.active:
            return False
        self.extension = min(self.extension + self.speed, self.max_ext)
        return self.extension >= self.max_ext

    def get_rect(self):
        """Get the rectangle [x, y, width, height] of the splitter in its current state."""
        rx, ry, rw, rh = self.region_rect
        ext = int(math.ceil(self.extension))
        if self.orientation == 'v':
            top = max(self.y - ext, ry)
            bottom = min(self.y + ext, ry + rh)
            return [self.x - 1, top, 3, bottom - top]
        else:
            left = max(self.x - ext, rx)
            right = min(self.x + ext, rx + rw)
            return [left, self.y - 1, right - left, 3]


class Game:
    """
    Main game class managing the game state, rendering, and game loop.
    """
    def __init__(self):
        # Pre-calculate sin/cos table for performance
        ANGLES = [i * 5 for i in range(int(360 / 5))]
        self.SIZE = 7  # Size of the balls
        self.COS_TABLE = {angle: math.cos(math.radians(angle)) for angle in ANGLES}
        self.SIN_TABLE = {angle: math.sin(math.radians(angle)) for angle in ANGLES}
        self.score = self.level = 0
        self.balls = []
        self.regions = {}
        self.splitter = None

    def init_game_assets(self):
        """Initialize graphics buffers and game assets."""
        dimgrob(2, 260, 179, 0)  # background
        dimgrob(3, 240, 159, 0)  # fill pattern
        dimgrob(7, 220, 70, 0x5F0000)   # digits
        dimgrob(1, 320, 240, 0x5F5F5F)  # backbuffer
        # Load ball sprite and UI elements
        ppleval('G6:=AFiles("assets.png");DimGrob_P(G4,7,7,#FF000000h);')
        strblit2(4, 0, 0, 7, 7, 6, 10, 10, 7, 7)  # ball
        strblit2(1, 0, 0, 12, 15, 6, 25, 0, 12, 15)
        strblit2(1, 12, 0, 308, 15, 1, 0, 0, 308, 15)
        blit(1, 0, 15, 1)
        # Draw game UI frame
        fillrect(1, 9, 179, 242, 46, 0xAD765F, 0x5F0000)
        fillrect(1, 259, 9, 52, 216, 0xAD765F, 0x5F0000)
        blit(2,0,0,1)
        # Draw UI text, score displays using PPL
        ppleval("""
        Local n,b=#5F0000h,c=#FFE4E4h,digits=Char(Asc("0123456789")+65248);
        TextOut_P("LEVEL",G1,267,15,3,c);
        TextOut_P("SHOTS",G1,264,88,3,c);
        TextOut_P("LIVES",G1,268,161,3,c);
        TextOut_P("AREA:",G1,16,183,3,c);
        TextOut_P("SCORE:",G1,16,205,3,c);
        TextOut_P("Arrows - move    Symb - orientation    Apps - split    Esc - exit",G1,14,228,1,#FFFFFFh);
        For n From -1 To 2 Do
          TextOut_P(digits,G7,n,-5,7,#FFFFFFh)
        End;
        Blit_P(G7,0,18,220,18+36,G7,0,0,220,18);
        For n From 0 To 8 Do
          Line_P(G7,0,n,220,n,{b,255-(16+n*14)});
          Line_P(G7,0,17-n,220,17-n,{b,255-(16+n*14)})
        End;
        For n From 19 To 36 Do
          Line_P(G7,0,n,220,n,{b,102+(n-19)*9});
          Line_P(G7,0,53-(n-19),220,53-(n-19),{b,102+(n-19)*9})
        End;
        Rect_P(G7,0,54,49,69,#007F00h);
        TextOut_P(Char(Concat(Makelist(X,X,8320,8329),65130)),G7,0,54,3,#FFFFFFh,220);
        Blit_P(G1,61,185,G7,50,58,57,67);
        """)

    def init_title_assets(self):
        """
        Prerenders rotated 'JezzBall' title text segments
        into a buffer (G8) to avoid real-time rotation calculations.
        """
        ppleval("""
        Local n,m,title=Char(Asc("JezzBall")+65248);
        DimGrob_P(G1,180,24,#0000FBh);
        DimGrob_P(G8,45,360,#FF000000h);
        For n From 1 To 16 Do
          For m From 1 To 2 Do
            TextOut_P(Mid(title,1,8),G1,m,2,7,0)
          End;
        End;
        For n From -2 To 1 Do
          For m From 1 To 2 Do
            TextOut_P(MID(title,1,8),G1,n,0,7,#FFFE70h)
          End;
        End;
        For n From 0 To 7 Do
          DimGrob_P(G2,45,45,#FF000000h);
          Blit_P(G2,0,0,45,45,G1,n*22+2,2,(n+1)*22+2,26,#0000FBh);
          DimGrob_P(G3,45,45,#FF000000h);
          Rotate(G3,(((n-3.5)*10))*pi/180,G2,22,22);
          Blit_P(G8,0,n*45,G3);
        End;
        """)

    def title(self):
        """Display the animated title screen and wait for Enter/Esc."""
        return ppleval(
        """
        Local t, c=(160,120), r=Exp(i*Pi/360), cnt, b={}, tris={}, idx, d=3;  
        Local lt, title={{15,43},{46,26},{83,13},{120,7},{158,8},{196,15},{232,28},{264,48}};
        Local offset={{1,0},{2,1},{2,2},{1,3},{0,3},{-1,2},{-1,1},{0,0}};
        Local author=Replace(Char(Asc("by Piotr Kowalewski")+65248),Char(65280),"    ");
        Local hs,hsstr,m;
        IfErr
          hs:=AFilesB("hs",0,4);
          hs:={hs[1]*65536+hs[2]*256+hs[3],hs[4]}
        Then
          AFilesB("hs"):={0,0,0,0};
          hs:={0,0}
        End;
        hsstr:={RIGHT("00000"+hs[1],6),RIGHT("0"+hs[2],2)};

        DimGrob_P(G1,320,240);
        For cnt From 1 To 16 Do
          b:=Concat(b, c + 210 * Exp(i * Pi/8 * (cnt - 1)));
          tris:=Concat(tris, {{1, cnt+1, IfTE(cnt = 16,2,cnt+2), IfTE(cnt mod 2 = 1,#0000FFh,#0000D8h)}})
        End;

        While IsKeyDown(4) or IsKeyDown(30) Do End;

        t:=Ticks;
        Repeat
          t:=t+25;
          b:=c+(b-c)*r;
          Triangle_P(G1,{
            {Re(c),Im(c)},
            {Re(b[1]),Im(b[1])}, {Re(b[2]),Im(b[2])}, {Re(b[3]),Im(b[3])}, {Re(b[4]),Im(b[4])}, {Re(b[5]),Im(b[5])}, {Re(b[6]),Im(b[6])}, {Re(b[7]),Im(b[7])}, {Re(b[8]),Im(b[8])}, {Re(b[9]),Im(b[9])}, {Re(b[10]),Im(b[10])}, {Re(b[11]),Im(b[11])}, {Re(b[12]),Im(b[12])}, {Re(b[13]),Im(b[13])}, {Re(b[14]),Im(b[14])}, {Re(b[15]),Im(b[15])}, {Re(b[16]),Im(b[16])}},
            tris);
          Rect_P(G1,159,119,161,121,#0000FFh);
          For cnt From 1 To 2 Do
            TextOut_P(author,G1,63,96,1,#FFFFFFh);
            TextOut_P("E N T E R - s t a r t",G1,84+cnt,127,5,#FFFFFFh);
            TextOut_P("E S C - e x i t",G1,84+cnt,149,5,#FFFFFFh)
          End;
          If hs[1]>0 Then
            TextOut_P("HIGH SCORE:",G1,5,210,2,#FFFFFFh);
            TextOut_P("LEVEL:",G1,142,210,2,#FFFFFFh);
            TextOut_P(hsstr[1],G1,79,204,4,#FFFF7Fh);
            TextOut_P(hsstr[2],G1,182,204,4,#FFFF7Fh)
          End;
          Rect_P(G1,0,224,319,239,{0,127});
          TextOut_P("v1.23, March-May 2025",G1,204,228,1,#EFEFEFh);
          lt:=title+offset;
          For cnt From 1 To 8 Do
            Blit_P(G1,lt[cnt],G8,0,(cnt-1)*45,40,(cnt-1)*45+45)
          End;
          d:=(d+1) mod 14;
          If d Mod 2 = 0 Then
            offset(0):=offset(1);
            offset:=Suppress(offset,1)
          End;
          Case
            If IsKeyDown(4) Then
              m:=0;
              Break;
            End;
            If IsKeyDown(30) Then
              m:=2;
              Break;
            End;
          End;
          While Ticks<t Do
            Wait(.001);
          End;
          Blit_P(G1);
        Until False;
        m;
        """)

    def reset_playfield(self):
        """Reset the game field for a new level."""
        # Clear the playfield
        fillrect(1, 9,9,242,161,0xAD765F,0)
        fillrect(2, 9,9,242,161,0xAD765F,0xFFFFC0)
        # Draw checkerboard pattern
        for i in range(15):
            for j in range(10):
                if (i + j) % 2:
                    fillrect(2, i*16+10, j*16+10, 16, 16, 0xFFFF90, 0xFFFF90)
        # Apply diagonal line pattern
        strblit2(3, 0, 0, 240, 159, 2, 10, 10, 240, 159)
        for i in range(-159, 240+159, 4):
            line(3, i, 159, i+159, 0, 0x9F9F9F)
            line(3, i+1, 159, i+160, 0, 0x9F9F9F)
        # Draw area percentage bar
        fillrect(1, 69, 186, 174, 10, 0x009F00, 0x003F00)
        line(1, 199, 184, 199, 197, 0xFFFF00)

    def generate_balls(self):
        """Generate balls for the current level."""
        coords_list = []
        # Place balls in non-overlapping positions
        while len(coords_list) < self.level:
            x = randint(20, 240 - self.SIZE)
            y = randint(20, 159 - self.SIZE)
            overlap = False
            for ex, ey in coords_list:
                if not (x + self.SIZE <= ex or ex + self.SIZE <= x or y + self.SIZE <= ey or ey + self.SIZE <= y):
                    overlap = True
                    break
            if not overlap:
                coords_list.append((x, y))
        # Set diagonal velocities for all balls
        diag = 1.5 / math.sqrt(2)
        speeds = [(diag, diag), (-diag, diag), (-diag, -diag), (diag, -diag)]
        self.balls = [Ball(x=x, y=y, vx=vx, vy=vy, region_id=0) for (x, y), (vx, vy) in zip(coords_list, [choice(speeds) for _ in range(self.level)])]

    def render_number(self, grob, number, x, y, type, l=0):
        """Draw a number on the screen using digit sprites."""
        n = enumerate("{:0{}}".format(number, l) if l else str(number))
        if type == 0:
            # Large digits
            for k, digit in n:
                strblit2(grob, x + k*18, y, 14, 35, 7, (ord(digit)-48)*22+4, 18, 14, 35)
        elif type == 1:
            # Medium digits
            for k, digit in n:
                strblit2(grob, x + k*16, y, 14, 18, 7, (ord(digit)-48)*22+4, 0, 14, 18)
        elif type == 2:
            # Small digits
            for k, digit in n:
                strblit2(grob, x + k*5, y, 5, 6, 7, (ord(digit)-48)*5, 64, 5, 6)

    def split_region(self, region_id):
        """Split a region into two parts based on the splitter position."""
        region = self.regions[region_id]
        rx, ry, rw, rh = region.rect
        cx, cy = self.splitter.x, self.splitter.y

        if self.splitter.orientation == 'v':
            # Vertical split
            left_width = cx - rx - 1
            right_width = rx + rw - (cx + 2)
        
            left_region = Region(region_id, [rx, ry, left_width, rh])
            new_id = max(self.regions.keys()) + 1
            right_region = Region(new_id, [cx + 2, ry, right_width, rh])
        
            self.regions[region_id] = left_region
            self.regions[new_id] = right_region
        
            # Reassign balls to the new regions
            for ball in self.balls:
                if ball.region_id == region_id:
                    ball.region_id = region_id if ball.x < cx else new_id
                
            return (region_id, new_id)
        else:
            # Horizontal split
            top_height = cy - ry - 1
            bottom_height = ry + rh - (cy + 2)
        
            top_region = Region(region_id, [rx, ry, rw, top_height])
            new_id = max(self.regions.keys()) + 1
            bottom_region = Region(new_id, [rx, cy + 2, rw, bottom_height])
        
            self.regions[region_id] = top_region
            self.regions[new_id] = bottom_region
        
            # Reassign balls to the new regions
            for ball in self.balls:
                if ball.region_id == region_id:
                    ball.region_id = region_id if ball.y < cy else new_id
                
            return (region_id, new_id)

    def check_collisions(self):
        """Check for collisions between balls."""
        balls = self.balls
        collisions = []
        n = len(balls)
        for i in range(n):
            c1x = balls[i].ix + 3
            c1y = balls[i].iy + 3
            for j in range(i+1, n):
                dx = (balls[j].ix + 3) - c1x
                dy = (balls[j].iy + 3) - c1y
                # Check if distance squared is less than or equal to radius squared
                if dx*dx + dy*dy <= 49:  # 7² = 49
                    collisions.append((i, j))
        return collisions

    def resolve_collision(self, idx1, idx2):
        """Handle collision between two balls."""
        b1, b2 = self.balls[idx1], self.balls[idx2]
        size = self.SIZE
        sin_tbl = self.SIN_TABLE
        cos_tbl = self.COS_TABLE
        
        # Calculate centers and normal vectors
        center1 = [b1.x + size / 2, b1.y + size / 2]
        center2 = [b2.x + size / 2, b2.y + size / 2]
        diff_x, diff_y = center2[0] - center1[0], center2[1] - center1[1]
        dist = math.sqrt(diff_x**2 + diff_y**2) or 0.001
        nx, ny = diff_x / dist, diff_y / dist
        tx, ty = -ny, nx  # Tangent vector
        
        # Calculate velocity components
        v1n = b1.vx * nx + b1.vy * ny  # Normal component of velocity
        v1t = b1.vx * tx + b1.vy * ty  # Tangent component of velocity
        v2n = b2.vx * nx + b2.vy * ny
        v2t = b2.vx * tx + b2.vy * ty
        
        # Swap normal components (elastic collision)
        v1n, v2n = v2n, v1n
        
        # Recalculate velocities
        b1.vx = v1n * nx + v1t * tx
        b1.vy = v1n * ny + v1t * ty
        b2.vx = v2n * nx + v2t * tx
        b2.vy = v2n * ny + v2t * ty
        
        SPEED = 1.5  # Constant speed for all balls after collision

        # Quantize angles to 5-degree increments for better gameplay
        for b in (b1, b2):
            angle = math.degrees(math.atan2(b.vy, b.vx))
            q_angle = int(round(angle/5)*5) % 360
            
            # Avoid horizontal and vertical directions (45°, 90°, etc.)
            if q_angle % 90 == 0:
                t = b.vx * tx + b.vy * ty
                delta = 5 if t >= 0 else -5
                q_angle = (q_angle + delta) % 360
                
            # Use lookup tables for performance
            b.vx = SPEED * cos_tbl[q_angle]
            b.vy = SPEED * sin_tbl[q_angle]

        # Handle physical overlap (push balls apart)
        overlap_x = min(b1.x + size, b2.x + size) - max(b1.x, b2.x)
        overlap_y = min(b1.y + size, b2.y + size) - max(b1.y, b2.y)
        if overlap_x * overlap_y >= 4:  # Minimum overlap threshold
            if overlap_x < overlap_y:
                correction = overlap_x / 2.0
                b1.x -= nx * correction
                b2.x += nx * correction
                b1.ix = int(b1.x + 0.5)
                b2.ix = int(b2.x + 0.5)
            else:
                correction = overlap_y / 2.0
                b1.y -= ny * correction
                b2.y += ny * correction
                b1.iy = int(b1.y + 0.5)
                b2.iy = int(b2.y + 0.5)

    def check_region_collision(self, ball):
        """Check if a ball is colliding with its region boundaries."""
        ix, iy = ball.ix, ball.iy
        x, y, w, h = self.regions[ball.region_id].rect
        size = self.SIZE
        # Return collision flags for left, right, top, bottom
        return (
            ix < x and ball.vx < 0,
            ix + size > x + w and ball.vx > 0,
            iy < y and ball.vy < 0,
            iy + size > y + h and ball.vy > 0
        )

    def resolve_region_collision(self, ball, collisions):
        """Handle collision between a ball and region boundaries."""
        x, y, w, h = self.regions[ball.region_id].rect
        left, right, top, bottom = collisions
        
        # Reverse velocity and adjust position
        if left:
            ball.vx *= -1
            ball.x = x
            ball.ix = int(ball.x + 0.5)
        elif right:
            ball.vx *= -1
            ball.x = x + w - self.SIZE
            ball.ix = int(ball.x + 0.5)
        
        if top:
            ball.vy *= -1
            ball.y = y
            ball.iy = int(ball.y + 0.5)
        elif bottom:
            ball.vy *= -1
            ball.y = y + h - self.SIZE
            ball.iy = int(ball.y + 0.5)

    def check_splitter_collisions(self):
        """Check if any ball is colliding with the active splitter."""
        x0, y0, w, h = self.splitter.get_rect()
        size = self.SIZE
        for ball in self.balls:
            if ball.region_id != self.splitter.region_id:
                continue
            bx, by = ball.ix, ball.iy
            # Check for rectangle overlap
            if bx < x0 + w and bx + size > x0 and by < y0 + h and by + size > y0:
                overlap_w = min(bx + size, x0 + w) - max(bx, x0)
                overlap_h = min(by + size, y0 + h) - max(by, y0)
                if overlap_w * overlap_h >= 3:  # Minimum overlap area
                    return True
        return False

    def wait_key(self, key_id):
        """Wait for a specific key to be pressed and released."""
        while not keyboard() & key_id:
            pass
		# After key press, wait until the key is released
        while keyboard() & key_id:
            pass

    def save_highscore(self):
        """Saves the current score as a high score if it beats the previous record."""
        # Open the high score file and read existing data
        with FileIO("hs", "rb") as f:
            data = f.read(4)
            # If file doesn't exist or data is invalid, initialize with zeros
            hs, hl = (0, 0) if len(data) != 4 else (int.from_bytes(data[:3], 'big'), data[3])
		
        # Check if current score beats the high score
        # A higher score always wins, or if scores are equal, a higher level wins
        if self.score > hs or self.score == hs and self.level > hl:
            # Save the new high score to file
            with FileIO("hs", "wb") as f:
                # Write score as 3 bytes and level as 1 byte
                f.write(self.score.to_bytes(3, 'big') + self.level.to_bytes(1, 'big'))

    def game_loop(self):
        # Initialize keyboard holding state
        kbd_hold = 1
        # Initialize game state variables
        frame = lives = self.score = self.level = 0
        gameplay = True
        # Initialize game assets (graphics, UI elements)
        self.init_game_assets()

        # Main game loop - continues until player exits or loses
        while gameplay:
            # Reset game state for new level
            shots = 0  # Number of splitter shots used
            filled_area = 0  # Area filled by successful splits
            self.level += 1  # Increment level
            lives = self.level  # Set lives equal to current level
            # Create splitter with speed that increases with level
            self.splitter = Splitter(131, 89, 'v', 0.95 + self.level * 0.05)
            # Reset the game field for new level
            self.reset_playfield()     
            # Create balls for the current level
            self.generate_balls()
            # Initialize regions (playable areas)
            self.regions = {0: Region(0, [10, 10, 240, 159])}
            # Display level number on UI
            self.render_number(1, self.level, 269, 34, 0, 2)
            # Display shots count on UI
            self.render_number(1, shots, 269, 107, 0, 2)
            # Display lives count on UI
            self.render_number(1, lives, 269, 180, 0, 2)
            # Draw background elements
            strblit2(1, 10, 10, 240, 159, 2, 10, 10, 240, 159)
            blit(0, 0, 0, 1)
            # Flag to indicate that the entire screen needs redrawing
            full_refresh = True
            splitter = self.splitter
            # Get initial time for frame rate control
            t = int(ppleval("Ticks"))
            
            # Level loop - continues until level is completed or player loses
            while True:
                # Control frame timing (roughly 50 FPS)
                t += 20
                frame += 1
                # Get keyboard input
                kbd = keyboard() & 0xFFFFFFFF

                # Handle keyboard input
                if kbd:
                    # ESC key - exit game
                    if kbd == 16:
                        gameplay = False
                        break

                    # Handle splitter movement and activation when it's not active
                    if not splitter.active:
                        # Handle keyboard key holding speed ramping
                        if kbd_hold > 1 and kbd_hold < 6:
                            step = 0
                        else:
                            step = (kbd_hold & 1) * 3 if kbd_hold < 20 else 3 if kbd_hold < 45 else 6

                        if not kbd_hold:
                            # ENTER or APPS key - launch splitter if in valid region
                            if kbd in (1, 1 << 30):
                                for region in self.regions.values():
                                    if region.contains_point(splitter.x, splitter.y):
                                        splitter.launch(region)
                                        shots += 1
                                        full_refresh = True
                                        break
                            # SYMB key - toggle splitter orientation (horizontal/vertical)
                            elif kbd == 2:
                                splitter.toggle_orientation()
                        # Arrow keys - move splitter
                        elif kbd == 4:  # Up
                            splitter.move(0, -step)
                        elif kbd == 4096:  # Down
                            splitter.move(0, step)
                        elif kbd == 128:  # Left
                            splitter.move(-step, 0)
                        elif kbd == 256:  # Right
                            splitter.move(step, 0)
                    kbd_hold += 1
                else:
                    kbd_hold = 0

                # Handle mouse input for splitter positioning
                ms = mouse()[0]
                if ms and not splitter.active:
                    splitter.x = max(11, min(248, round(ms[0]/3) * 3 - 1))
                    splitter.y = max(11, min(167, round(ms[1]/3) * 3 - 1))

                # Handle screen refreshing
                if full_refresh:
                    # Redraw the entire screen
                    strblit2(1, 10, 10, 240, 159, 2, 10, 10, 240, 159)
                    self.render_number(0, shots if shots < 100 else '', 269, 107, 0, 2)
                    if shots >= 100:
                        strblit2(0, 301, 108, 9, 7, 6, 17, 10, 9, 7)
                    self.render_number(0, self.score, 68, 201, 1, 6)
                    strblit2(0, 70, 187, 172, 8, 1, 70, 187, 172, 8)
                    full_refresh = False
                elif lives >= 0:
                    # Clear old ball positions to prevent trails
                    for ball in self.balls:
                        ball.clear()
                else:
                    # Show game over screen when lives are depleted
                    ppleval("""
                    FillPoly_P({70,70,190,70,210,90,190,110,70,110,50,90},#3FFF5F00h);
                    TextOut_P("GAME OVER",76,70,6,#FFFFFFh);
                    TextOut_P("Press Esc",106,95,2,#FFFFFFh);
                    """)
                    # Save high score and wait for ESC key
                    self.save_highscore()
                    self.wait_key(1 << 4)
                    gameplay = False
                    break

                # Check if level is completed (75% of area filled)
                if filled_area / 38160 < 0.75:
                    # Update ball positions
                    for ball in self.balls:
                        ball.update_position()
                else:
                    # Render balls in their final positions
                    for ball in self.balls:
                        ball.render()
                    strblit2(0, 10, 10, 240, 159, 1, 10, 10, 240, 159)
                    # Show level completion message
                    ppleval("""
                    FillPoly_P({40,70,220,70,240,90,220,110,40,110,20,90},#2F007F00h);
                    TextOut_P("LEVEL COMPLETED",45,70,6,#FFFFFFh);
                    TextOut_P("Press Enter to continue",69,95,2,#FFFFFFh);
                    """)
                    # Save high score and wait for ENTER key to proceed
                    self.save_highscore()
                    self.wait_key(1 << 30)
                    break

                # Process ball collisions with each other
                for idx1, idx2 in self.check_collisions():
                    self.resolve_collision(idx1, idx2)
                
                # Process ball collisions with region boundaries
                for ball in self.balls:
                    collisions = self.check_region_collision(ball)
                    self.resolve_region_collision(ball, collisions)
                    ball.render()

                # Handle active splitter logic
                if splitter.active:
                    # Update splitter extension
                    done = splitter.update()
                    splitter.render_active()

                    # Check if balls collide with the splitter
                    if self.check_splitter_collisions():
                        # Ball hit the splitter - deactivate and lose a life
                        splitter.active = False
                        lives -= 1
                        if lives >= 0:
                            # Clear the splitter from screen
                            splitter.destroy()
                            # Update lives display
                            self.render_number(0, lives, 269, 180, 0, 2)
                    elif done:
                        # Splitter completed its extension - deactivate and split region
                        splitter.active = False
                        subreg1_id, subreg2_id = self.split_region(splitter.region_id)

                        # Check if any sub-region is empty (contains no balls)
                        empty_id = None
                        if sum(1 for b in self.balls if b.region_id == subreg1_id) == 0:
                            empty_id = subreg1_id
                        elif sum(1 for b in self.balls if b.region_id == subreg2_id) == 0:
                            empty_id = subreg2_id

                        # Process empty regions (fill them and add to score)
                        cleared = 0
                        if empty_id is not None:
                            rx, ry, rw, rh = self.regions[empty_id].rect
                            strblit2(2, rx, ry, rw, rh, 3, rx-10, ry-10, rw, rh)
                            cleared = rw * rh
                            del self.regions[empty_id]

                        # Render the splitter as a solid wall and calculate its area
                        splitter_area = splitter.render_closed()

                        # Calculate score based on area filled
                        total = cleared + splitter_area
                        if total > 0:
                            filled_area += total
                            base = total // 9
                            self.score += math.floor(base * (1 + base / 38160) ** 3 * (1 + 0.2 * (self.level - 1)))

                        # Update progress bar for filled area percentage
                        perc = filled_area / 38160
                        fillrect(1, 70, 187, int(172 * perc), 8, 0x007F00, 0x007F00)
                        line(1, 199, 187, 199, 194, 0xFFFF00)
                        if perc > 0.03:
                            self.render_number(1, int(perc * 100), (int(172 * perc) - (4 if perc < 0.1 else 10))//2 + 70, 188, 2)

                        full_refresh = True
                elif lives >= 0:
                    # When splitter isn't active, show waiting animation
                    splitter.render_waiting(frame)

                # Wait until next frame time
                while ppleval("Ticks") < t:
                    pass

                # Draw game area to screen
                strblit2(0, 10, 10, 240, 159, 1, 10, 10, 240, 159)
                if not full_refresh and lives >= 0:
                    # Clear the splitter if needed (for animation)
                    splitter.clear()

        # Game over - save high score
        self.save_highscore()


class JezzBall:
    """
    Main entry point class that manages game execution, handles environment setup/teardown,
    and controls the game flow between title screen and gameplay.
    """
    def __enter__(self):
        """
        Set up the game environment, save current calculator settings,
        configure optimal settings for the game, and initialize the Game instance.
        
        Returns:
            self: The JezzBall instance for context manager usage.
        """
        sep = ppleval('HSeparator')
        ppleval('HSeparator:=0')
        self.vars = tuple(ppleval('{AAngle,AFormat,AComplex,Bits}')) + (sep,)
        ppleval('AAngle:=1;AFormat:=1;AComplex:=0;Bits:=32')
        self.game = Game()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        This method is automatically called when exiting the game.
        
        It saves the high scores, clears graphic buffers, and restores
        previously saved calculator settings.
        
        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.
            
        Returns:
            bool | None: True if KeyboardInterrupt should be suppressed, otherwise None.
        """
        self.game.save_highscore()
        for n in range(1, 9):
            dimgrob(n, 0, 0, 0)
        ppleval('AAngle:=%d;AFormat:=%d;AComplex:=%d;Bits:=%d;HSeparator:=%d;TOff:=TOff' % self.vars)
        return exc_type is KeyboardInterrupt

    def run(self):
        """
        Main game execution method that creates the context manager,
        initializes title assets, and manages the game flow between 
        title screen and gameplay until the player exits the game.
        """
        with self:
            game = self.game
            game.init_title_assets()
            mode = 1
            while mode != 0:
                if mode == 1:
                    mode = game.title()
                elif mode == 2:
                    game.game_loop()
                    mode = 1

JezzBall().run()