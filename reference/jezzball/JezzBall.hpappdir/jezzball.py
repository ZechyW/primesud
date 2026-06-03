import uio
def d():
	with uio.FileIO('jezzball.bin')as f:B = memoryview(f.read());C=[];A=0;J=len(B);X=C.extend
	while A<J:
		H=B[A];A+=1;D=H&127
		if H&128:
			I=B[A]|B[A+1]<<8;A+=2;E=len(C)-I;F=D
			while F>0:G=min(F,I);X(C[E:E+G]);F-=G;E+=G
		else:X(B[A:A+D]);A+=D
	return bytes(C)
exec(compile(d(),'','exec'))