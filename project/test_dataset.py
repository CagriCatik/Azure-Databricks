import os
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
import matplotlib.pyplot as plt
from tqdm import tqdm
from geopy.distance import geodesic
import numpy as np

# Step 1: Define Functions to Read and Process Trajectory Files

def read_trajectory(file_path):
    """
    Read an individual trajectory file and return a DataFrame.
    """
    try:
        # Skip the first 6 header lines as they contain metadata
        df = pd.read_csv(
            file_path,
            skiprows=6,
            header=None,
            names=['latitude', 'longitude', 'zero', 'altitude', 'date_days', 'date', 'time']
        )
        # Create a geometry column with Point objects
        df['geometry'] = df.apply(lambda row: Point(row['longitude'], row['latitude']), axis=1)
        return df
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return pd.DataFrame()

def trajectory_to_geodataframe(df):
    """
    Convert a DataFrame to a GeoDataFrame with the appropriate CRS.
    """
    gdf = gpd.GeoDataFrame(df, geometry='geometry')
    gdf.set_crs(epsg=4326, inplace=True)  # WGS84 Latitude/Longitude
    return gdf

# Step 2: Process All Trajectories for Users

def process_user_trajectories(user_path):
    """
    Process all trajectory files for a given user.
    """
    trajectories = []
    traj_path = os.path.join(user_path, 'Trajectory')
    if not os.path.exists(traj_path):
        return trajectories
    for file in os.listdir(traj_path):
        if file.endswith('.plt'):
            file_path = os.path.join(traj_path, file)
            df = read_trajectory(file_path)
            if not df.empty:
                gdf = trajectory_to_geodataframe(df)
                trajectories.append(gdf)
    return trajectories

base_path = 'geolife_trajectories/data'

all_users = os.listdir(base_path)[:1]  # Process only the first 5 users
#all_users = os.listdir(base_path)     # all users
all_trajectories = []

for user in tqdm(all_users, desc='Processing Users'):
    user_path = os.path.join(base_path, user)
    if os.path.isdir(user_path):
        user_trajectories = process_user_trajectories(user_path)
        all_trajectories.extend(user_trajectories)

# Step 3: Convert Point Sequences to LineStrings

def create_linestring(gdf):
    """
    Create a LineString from a sequence of points in a GeoDataFrame.
    """
    coords = gdf['geometry'].tolist()
    if len(coords) < 2:
        return None
    line = LineString(coords)
    return line

# Create GeoDataFrame of Trajectories

trajectory_lines = []

for traj in tqdm(all_trajectories, desc='Creating LineStrings'):
    line = create_linestring(traj)
    if line is not None:
        trajectory_lines.append({'geometry': line})

trajectories_gdf = gpd.GeoDataFrame(trajectory_lines)
trajectories_gdf.set_crs(epsg=4326, inplace=True)

# Step 4: Clean and Prepare Data for Plotting

# Check for invalid geometries
invalid_geometries = trajectories_gdf[~trajectories_gdf.is_valid]

if not invalid_geometries.empty:
    print("Found invalid geometries. Dropping them.")
    trajectories_gdf = trajectories_gdf[trajectories_gdf.is_valid]

# Check for geometries with extreme coordinates
def has_extreme_coords(geom):
    try:
        for coord in geom.coords:
            if not (-180 <= coord[0] <= 180) or not (-90 <= coord[1] <= 90):
                return True
    except NotImplementedError:
        # For geometries that do not support coords (e.g., empty geometries)
        return True
    return False

extreme_geometries = trajectories_gdf[trajectories_gdf['geometry'].apply(has_extreme_coords)]

if not extreme_geometries.empty:
    print("Found geometries with extreme coordinates. Dropping them.")
    trajectories_gdf = trajectories_gdf[~trajectories_gdf.index.isin(extreme_geometries.index)]

# Drop empty or null geometries
trajectories_gdf = trajectories_gdf[~trajectories_gdf['geometry'].is_empty]
trajectories_gdf = trajectories_gdf.dropna(subset=['geometry'])

# Ensure CRS is set correctly
if trajectories_gdf.crs is None:
    trajectories_gdf.set_crs(epsg=4326, inplace=True)

# Step 5: Visualize the Trajectories

# Load a World Map from Natural Earth
world = gpd.read_file('https://naturalearth.s3.amazonaws.com/50m_cultural/ne_50m_admin_0_countries.zip')

# Plot Trajectories on the World Map
fig, ax = plt.subplots(figsize=(15, 10))
world.plot(ax=ax, color='lightgray')

# Plot Trajectories
trajectories_gdf.plot(ax=ax, linewidth=0.5, color='blue')

ax.set_aspect('equal')  # Manually set aspect ratio
plt.title('Geolife Trajectories')
plt.xlabel('Longitude')
plt.ylabel('Latitude')
plt.show()

# Optional: Zoom into Specific Regions (e.g., Beijing)
# Uncomment the following lines to zoom into Beijing area
# minx, miny, maxx, maxy = (115, 39, 117, 41)
# ax.set_xlim(minx, maxx)
# ax.set_ylim(miny, maxy)
# plt.show()

# Step 6: Analyze the Trajectories

# Recalculate distances for the trajectories in trajectories_gdf

trajectory_distances = []

for idx, row in tqdm(trajectories_gdf.iterrows(), total=trajectories_gdf.shape[0], desc='Calculating Distances'):
    coords = list(row['geometry'].coords)
    if len(coords) < 2:
        total_distance = 0
    else:
        distances = [
            geodesic((coords[i][1], coords[i][0]), (coords[i+1][1], coords[i+1][0])).kilometers
            for i in range(len(coords)-1)
        ]
        total_distance = sum(distances)
    trajectory_distances.append(total_distance)

# Add Distance Information to Trajectories GeoDataFrame
trajectories_gdf['distance_km'] = trajectory_distances

# Optional: Save the Trajectories with Distances to a File
# trajectories_gdf.to_file('trajectories_with_distances.geojson', driver='GeoJSON')

# Step 7: Clustering Trajectories (Optional)

# Uncomment the following code to perform clustering

# Extract coordinates from LineStrings
# coords = []
# for line in trajectories_gdf['geometry']:
#     coords.extend(list(line.coords))

# coords = np.array(coords)

# Perform DBSCAN clustering
# db = DBSCAN(eps=0.01, min_samples=10, algorithm='ball_tree', metric='haversine').fit(np.radians(coords))
# labels = db.labels_

# Add cluster labels to a GeoDataFrame
# points_gdf = gpd.GeoDataFrame(geometry=[Point(xy) for xy in coords], crs='EPSG:4326')
# points_gdf['cluster'] = labels

# Plot clusters
# fig, ax = plt.subplots(figsize=(15, 10))
# world.plot(ax=ax, color='lightgray')
# points_gdf.plot(ax=ax, column='cluster', cmap='rainbow', markersize=5, legend=True)
# plt.title('Clustered Trajectory Points')
# plt.xlabel('Longitude')
# plt.ylabel('Latitude')
# plt.show()
