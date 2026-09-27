java -cp out sim.app.GenerateMain --N 100 --obstacles 01_centro.txt
java -cp out sim.app.SimulateMain --obstacles 01_centro.txt    
python3 analysis/resumen_t90.py --traj output/particles.txt --n 100

15.0 14.474097 15.057460 16.168675 14.885149

python3 analysis/promedio_desvio.py 