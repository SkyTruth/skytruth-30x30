# import subprocess

# def json2mbtiles(
#     bucket: str,
#     input_file: str,
#     output_file: str,
# ) -> None:

#     # https://github.com/mapbox/tippecanoe
#     # -zg: Automatically choose a maxzoom that should be sufficient to clearly distinguish the
#     #   features and the detail within each feature
#     # -f: Deletes existing files in location with the same name
#     # -P: reads the geojson in parallel if the file is newline delimited
#     # -o: The following argurment is hte output path
#     # -ae:  Increase the maxzoom if features are still being dropped at that zoom level
#     subprocess.run(
#         f"tippecanoe -zg -f -P -o {output_file} -ae {input_file}",
#         shell=True,
#         check=True,
#     )
#     input_file.unlink()
#     # return output_path


# def mbtileGeneration(
#     data_path: Path,
#     output_path: Union[Path, None] = None,
#     update: bool = False,
#     **kwargs: ExcessParams,
# ) -> Path:
#     """
#     generate mbtiles file from geomtry file

#     Args:
#         data_path (Path): The path to the file.
#         output_path (Union[Path, None], optional): The path to the output file.
# The default is None.
#         update (bool, optional): Whether to update the mbtiles file. The default is False.

#     Returns:
#         Path: The path to the output file.

#     """
#     try:
#         if not data_path.exists():
#             raise FileNotFoundError("Data path does not exist.")

#         if not output_path:
#             output_path = data_path.with_suffix(".mbtiles")

#         if update or not output_path.exists():
#             if data_path.suffix != ".json":
#                 data_path = simplifyGeometries2Json(data_path, **kwargs)
#             if data_path.suffix != ".json":
#                 raise Exception("Data path must be a json file.")

#             logging.info("Creating mbtiles file...")
#             json2mbtiles(data_path, output_path, **kwargs)

#         return output_path

#     except Exception as e:
#         raise e
