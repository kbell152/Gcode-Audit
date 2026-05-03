(Made in : Autodesk CAM Post Processor)
(G-Code optimized for Grbl 1.1 / BlackBox controller)
(OpenBuilds CNC : GRBL/BlackBox)
(Post-Processor : OpenbuildsFusion360PostGrbl.cps V1.0.46)
(Units = mm)

(Arcs are limited to the XY plane: if you want vertical arcs then)
(edit allowedCircularPlanes in the CPS file)

(Drawing name : vacuum_spoilboard_first_cell_v1.3)
(Program Name : vacuum_spoilboard_first_cell_v1.3)
(Program Comments : Full job - all 4 operations)
(Stock : XxYxZ : 1.2e3x2.5e3x19)

(4 Operations :)
(1 : Cell vacuum seal)
(  Work Coordinate System : G54)
(  Tool 1: Flat End Mill 2 Flutes, Diam = 6.35mm, Len = 19.05mm)
(  Spindle : RPM = 18000 other)
(  Machining time : 0h:16m:12s)
(2 : Pre-drill vacuum feeders)
(  Work Coordinate System : G54)
(  Tool 1: Flat End Mill 2 Flutes, Diam = 6.35mm, Len = 19.05mm)
(  Spindle : RPM = 18000 other)
(  Machining time : 0h:0m:11s)
(3 : Create pockets and channel matrix)
(  Work Coordinate System : G54)
(  Tool 1: Flat End Mill 2 Flutes, Diam = 6.35mm, Len = 19.05mm)
(  Spindle : RPM = 18000 other)
(  Machining time : 0h:43m:30s)
(4 : Cleanup missed channels)
(  Work Coordinate System : G54)
(  Tool 1: Flat End Mill 2 Flutes, Diam = 6.35mm, Len = 19.05mm)
(  Spindle : RPM = 18000 other)
(  Machining time : 0h:29m:36s)
(Total Machining time : 1h:29m:31s)


G90 G94 G17
G21

(When using Fusion for Personal Use, the feedrate of rapid)
(moves is reduced to match the feedrate of cutting moves,)
(which can increase machining time. Unrestricted rapid moves)
(are available with a Fusion Subscription.)

(Operation 1 of 4 : Cell vacuum seal)
G54
(G53 retract removed - no limit switches; using G54 safe Z instead)
G0 Z25.4
G0 X74.879 Y74.917
M3 S18000
G4 P1.8
G0 X74.879 Y74.917 Z15
G0 Z5
G1 Z2.5 F500
Z-1.058
X74.885 Y74.948 Z-1.255
X74.894 Y75.038 Z-1.432
X74.891 Y75.108 Z-1.502
X74.881 Y75.177 Z-1.572
X74.858 Y75.263 Z-1.617
X74.823 Y75.344 Z-1.662
X74.772 Y75.427 Z-1.678
X74.708 Y75.502 Z-1.693
G2 X66.338 Y95.707 I20.206 J20.206 F1800
G1 Y767.893
G2 X94.914 Y796.468 I28.575 J0
G1 X513.099
G2 X541.674 Y767.893 I0 J-28.575
G1 Y95.707
G2 X513.099 Y67.132 I-28.575 J0
G1 X94.913
G2 X74.708 Y75.502 I0 J28.575
G1 X74.484 Y75.595
X74.26 Y75.503
X72.689 Y73.947
X72.595 Y73.722
X72.688 Y73.497
G3 X88.411 Y66.98 I15.723 J15.708
G1 X94.913
X519.601
G3 X541.826 Y89.205 I0 J22.225
G1 Y774.395
G3 X519.601 Y796.62 I-22.225 J0
G1 X88.411
G3 X66.186 Y774.395 I0 J-22.225
G1 Y89.205
G3 X72.688 Y73.497 I22.225 J0
G1 X72.87 Y73.474
X72.938 Y73.643
X72.815 Y74.082
X72.666 Y74.192
X72.524 Y74.074
Z-2.752 F500
X72.518 Y74.043 Z-2.948
X72.51 Y73.953 Z-3.125
X72.512 Y73.883 Z-3.195
X72.522 Y73.814 Z-3.265
X72.545 Y73.728 Z-3.31
Z0.25
G1 Z-5.35 F700
Z-9.525
Y698.895 F2800
X178.594
G0 Z25.4
(G53 end-of-job retract removed - no limit switches)
M5
G0 X-10 Y-10
M30
