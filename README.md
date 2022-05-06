# graf_filling_level
Dieses Projekt berechnet den Zusammenhang zwischen Füllhöhe und Volumen der Graf Regenwasser Tanks.
Die Ergebnisse sind im Ordner `Output` zu finden.

This project calulates the volume height relation of graf rainwater tanks.
The results are collected in the `output/output.csv` for every centimeter fill height.
To visualize the filling curves the results are plotted like this:

![Platin5000 filling curve](/output/Platin_5000.png)

Following tank systems are listed:
- Platin
- Platin XL
- Platin XXL
- Carat
- Carat XL
- Carat XXL


# Method
To get the tank volume dependend on the filling height a 3D model of the tanks is needed.
This was exported as `.stl` from the by the manufacturer provided Revit model.
Unfortunately this model is not watertight, so volume computation is not easy.
The script `CalcFillingLevel.py` solves this problem by:
1. reading the `.stl` from file
2. transforming the model to a voxel-based representation
3. finding all inner voxels (tank volume voxels)
4. summing volume voxels up while incrementing the z-axis

The tank systems built of multiple parts (Carat/Platin XXL) are calculated as the sum of the used parts.

# Software
This Python script uses the `trimesh` library to load and voxelize the models.
The current implementation calulates all models (located at `/data`) in one run, this takes a while (~1 hour).
I implemented a simple solution, no speed optimization / parallelization was done.
