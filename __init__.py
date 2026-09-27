# Siemen Lens

bl_info = {
    "name": "AutoTrack",
    "author": "Siemen Lens",
    "version": (5, 1, 2),  # on publish : don't forget to update version in about menu too
    "blender": (4, 0, 0),
    "location": "Movie Clip Editor > Sidebar > AutoTrack Tab",
    "description": "Automatically track imported footage with optimized solving logic.",
    "category": "VFX",
}

# imports necessary to make the script work
import bpy
import math
import random
import time

try:
    import aud
    aud_present = True
except:
    aud_present = False
from pathlib import Path

# Shared UI definitions
zone_types = [
    ('OPT1', "Exclude", "Exclude the annotated area from tracking", 'FULLSCREEN_ENTER', 1),
    ('OPT2', "Only", "Only keep annotated area in tracking", 'FULLSCREEN_EXIT', 2)
]


# Helper function for Object Mapping Constraint Updates
def update_constraint(self, context):
    track_obj_name = self.name
    target_obj = self.obj

    # Try to grab the clip from context directly first, or fall back to finding it in the UI
    clip = getattr(context, "edit_movieclip", None)
    if not clip:
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'CLIP_EDITOR':
                    if area.spaces.active and getattr(area.spaces.active, "clip", None):
                        clip = area.spaces.active.clip
                        break

    # 1. Remove constraints for this tracking object from ALL scene objects to ensure exclusivity
    for obj in bpy.data.objects:
        # --- NEW: Skip generated surface meshes so they stay linked! ---
        if "_PointCloudSurface" in obj.name:
            continue
        # ---------------------------------------------------------------

        to_remove = []
        for c in obj.constraints:
            if c.type == 'OBJECT_SOLVER' and c.object == track_obj_name:
                if clip:
                    if getattr(c, "clip", None) == clip:
                        to_remove.append(c)
                else:
                    to_remove.append(c)
        for c in to_remove:
            obj.constraints.remove(c)

    # 2. Add constraint to the new target_obj (if not None)
    if target_obj and clip:
        c = target_obj.constraints.new('OBJECT_SOLVER')
        c.clip = clip
        c.object = track_obj_name


# Helper functions for the custom Distance Scale slider
def get_distance_scale(self):
    clip = getattr(bpy.context, "edit_movieclip", None)
    if clip:
        track_obj = clip.tracking.objects.get(self.name)
        if track_obj:
            return track_obj.scale
    return 1.0

def set_distance_scale(self, value):
    clip = getattr(bpy.context, "edit_movieclip", None)
    if clip:
        track_obj = clip.tracking.objects.get(self.name)
        if track_obj:
            track_obj.scale = value

# Data model for linking Object Track to 3D Scene Object and Annotation State
class AutoTrackObjectMapping(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    obj: bpy.props.PointerProperty(type=bpy.types.Object, update=update_constraint)
    use_annotation: bpy.props.BoolProperty(
        name="Use Annotations",
        description="Create zones using the annotation feature for this tracking object",
        default=True
    )
    annotation_mode: bpy.props.EnumProperty(
        name="Annotation Mode",
        description="What mode should annotation work in?",
        items=zone_types,
        default='OPT1'
    )
    distance_scale: bpy.props.FloatProperty(
        name="Distance (Scale)",
        description="Adjust the scale of the object solution in camera space",
        get=get_distance_scale,
        set=set_distance_scale,
        min=0.0,  # Mathematically blocks negative values, but provides no visual wall
        step=1,  # 1 = an entire screen drag (approx 1000px) changes the value by 10
        precision=5
    )
# Class to instantly switch the active tracking object and sync the annotation immediately
class SetActiveTrackObject(bpy.types.Operator):
    bl_idname = "autotrack.set_active_track_object"
    bl_label = "Set Active Track Object"
    bl_description = "Set this tracking object as active"
    bl_options = {'REGISTER', 'UNDO'}

    obj_name: bpy.props.StringProperty()

    def execute(self, context):
        clip = getattr(context, "edit_movieclip", None)
        if not clip:
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'CLIP_EDITOR':
                        if area.spaces.active and getattr(area.spaces.active, "clip", None):
                            clip = area.spaces.active.clip
                            break

        if clip:
            track_obj = clip.tracking.objects.get(self.obj_name)
            if track_obj:
                clip.tracking.objects.active = track_obj

                # Force instant annotation swap for immediate visual feedback
                expected_name = f"Ann_{clip.name}_{track_obj.name}"
                attr_name = "annotation" if hasattr(clip, "annotation") else "grease_pencil"
                data_storage = bpy.data.annotations if hasattr(bpy.data, "annotations") else bpy.data.grease_pencils

                target_gp = data_storage.get(expected_name)
                if target_gp:
                    setattr(clip, attr_name, target_gp)
                else:
                    try:
                        new_gp = data_storage.new(expected_name)
                        setattr(clip, attr_name, new_gp)
                    except:
                        setattr(clip, attr_name, None)

        return {'FINISHED'}


# Class to remove a specific tracking object via the 'X' button
class RemoveTrackObject(bpy.types.Operator):
    bl_idname = "autotrack.remove_track_object"
    bl_label = "Remove Track Object"
    bl_description = "Remove this tracking object"
    bl_options = {'REGISTER', 'UNDO'}

    obj_name: bpy.props.StringProperty()

    def execute(self, context):
        clip = getattr(context, "edit_movieclip", None)
        if not clip:
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'CLIP_EDITOR':
                        if area.spaces.active and getattr(area.spaces.active, "clip", None):
                            clip = area.spaces.active.clip
                            break

        if clip:
            track_obj = clip.tracking.objects.get(self.obj_name)
            if track_obj:
                if len(clip.tracking.objects) > 1:
                    clip.tracking.objects.active = track_obj

                    # Requires proper context override to perform clip operations from UI
                    area_found = False
                    for window in context.window_manager.windows:
                        for area in window.screen.areas:
                            if area.type == 'CLIP_EDITOR':
                                with context.temp_override(window=window, area=area):
                                    bpy.ops.clip.tracking_object_remove()
                                area_found = True
                                break
                        if area_found:
                            break

                    if not area_found:
                        bpy.ops.clip.tracking_object_remove()

                    # Cleanup mapping
                    mapping_idx = context.scene.at_object_mappings.find(self.obj_name)
                    if mapping_idx >= 0:
                        context.scene.at_object_mappings.remove(mapping_idx)
                else:
                    self.report({'WARNING'}, "Cannot remove the last tracking object.")
        return {'FINISHED'}


# class for the main automatic tracking process
class Runtracking(bpy.types.Operator):
    bl_idname = "autotrack.runtracking"
    bl_label = "Start Tracking!"
    bl_description = "Run the tracking process"
    bl_options = {'REGISTER'}

    def update_camera_parameters(self, context):
        # check what preset is used for the sensor size
        clip = context.edit_movieclip
        if context.scene.option_sensor_dropdown == "OPT1":
            clip.tracking.camera.sensor_width = 34
        if context.scene.option_sensor_dropdown == "OPT2":
            clip.tracking.camera.sensor_width = 22
        if context.scene.option_sensor_dropdown == "OPT3":
            clip.tracking.camera.sensor_width = 17
        if context.scene.option_sensor_dropdown == "OPT4":
            clip.tracking.camera.sensor_width = 9
        if context.scene.option_sensor_dropdown == "OPT5":
            pass

        # set the focal length option to the one the user defined in the PT panel, same with the tripod option
        clip.tracking.camera.focal_length = self.option_focallength
        clip.tracking.settings.use_tripod_solver = context.scene.option_tripod

        if not clip or not clip.tracking.camera:
            return
        context.scene.resolve_buttonvisible = True

    # define the preset sensor types along with their icons and tooltips
    sensor_types = [
        ('OPT1', "Full Frame", "Use Full Frame as the Sensor Type (default)", 'FULLSCREEN_ENTER', 34),
        ('OPT2', "Crop Sensor", "Use Crop Sensor as the Sensor Type", 'FULLSCREEN_EXIT', 22),
        ('OPT3', "Micro Four-Thirds", "Use Micro Four Thirds as the Sensor Type", 'CHECKBOX_DEHLT', 17),
        ('OPT4', "Mainstream Smartphone", "Use a Smartphone Sensor as the Sensor Type", 'BORDERMOVE', 9),
        ('OPT5', "Custom", "Use a Custom Sensor Type", 'CON_SAMEVOL', 1)
    ]

    filter_passes = [
        ('OPT1', "Fast Pass (Legacy)",
         "Use a simple and fast filtering algorithm, not very versatile and may not work.", 'PIVOT_MEDIAN', 1),
        ('OPT2', "Single Pass", "Only clean bad markers with a single pass (without a second solver sequence)",
         'PIVOT_ACTIVE', 2),
        ('OPT3', "Dual Pass",
         "Clean bad markers using a dual pass system, This will clean more accurately but takes longer. This second pass will only run if the solve error is still unusable. (Recommended Option)",
         'PIVOT_INDIVIDUAL', 3)
    ]

    # defining of variables and parameters
    bpy.types.Scene.option_focallength = bpy.props.FloatProperty(
        name="Focal Length",
        description="The focal length of the lens used to record the video. You can always change this after the tracking to fine-tune. If you enter the equivalent focal length, set the sensor size to Full Frame.",
        default=30,
        update=update_camera_parameters
    )

    bpy.types.Scene.option_sensor_dropdown = bpy.props.EnumProperty(
        name="Sensor",
        description="Choose your Camera sensor type, if you don't know it, leave it at full frame",
        items=sensor_types,
        default='OPT1',
        update=update_camera_parameters
    )

    bpy.types.Scene.option_markerthreshold = bpy.props.FloatProperty(
        name="Marker's Threshold",
        default=0.01,
        min=0.0001,
        max=3.0,
        description="Threshold of placing markers"
    )
    bpy.types.Scene.option_markerscale = bpy.props.FloatProperty(
        name="Marker's Scale",
        default=100,
        min=50,
        max=500,
        subtype='PERCENTAGE',
        description="Scale of the placed markers"
    )

    bpy.types.Scene.option_solveriterations = bpy.props.IntProperty(
        name="Solver Iterations",
        default=10,
        min=3,
        max=50,
        description="Amount of times it'll try to solve the tracking for a better result"
    )
    bpy.types.Scene.option_refinefocallength = bpy.props.BoolProperty(
        name="Refine Focal Length",
        description="Refines the focal length you've entered. Enable this if you're not really sure of your focal length.",
        default=True
    )
    bpy.types.Scene.option_refinedistortion = bpy.props.BoolProperty(
        name="Refine Distortion",
        description="Calculates distortion on your clip, enable this if your clip has radial distortion.",
        default=False
    )

    bpy.types.Scene.option_markerdistance = bpy.props.IntProperty(
        name="Marker's Distance",
        default=75,
        min=5,
        max=500,
        description="Marker's minimum distance from each other relative to the video resolution"
    )

    bpy.types.Scene.option_marker_frame_interval = bpy.props.IntProperty(
        name="Maximum Interval",
        default=75,
        min=25,
        max=100,
        description="Maximum frame interval before intervening with the automatic substep system"
    )
    bpy.types.Scene.option_min_track_length = bpy.props.IntProperty(
        name="Minimum Track Length",
        default=75,
        min=30,
        max=100,
        description="Minimum length of a Substep frame track."
    )

    bpy.types.Scene.option_tracks_prefiltering_perc = bpy.props.FloatProperty(
        name="Keep Tracks Prefilter %",
        default=80,
        min=50,
        max=100,
        description="How many tracks to keep during prefilter pass",
        subtype="PERCENTAGE",
    )

    bpy.types.Scene.option_tracks_cleanup_perc = bpy.props.FloatProperty(
        name="Keep Tracks Cleanup %",
        default=60,
        min=50,
        max=100,
        description="How many % of tracks to keep during Cleanup pass",
        subtype="PERCENTAGE",
    )

    bpy.types.Scene.option_filterpasses = bpy.props.EnumProperty(
        name="Filter",
        description="What algorithm should be used to clean bad markers?",
        items=filter_passes,
        default='OPT3'
    )

    bpy.types.Scene.option_markers_retention = bpy.props.IntProperty(
        name="Marker Retention Rate",
        description="The threshold of how many markers are left before we should add new markers",
        subtype='PERCENTAGE',
        min=10,
        max=90,
        default=50
    )

    bpy.types.Scene.at_status = bpy.props.StringProperty(
        name="Status",
        default="AutoTrack Status"
    )
    bpy.types.Scene.at_bestsolve = bpy.props.StringProperty(
        name="Best Solve",
        default="Best Solve"
    )

    bpy.types.Scene.option_setsceneframe = bpy.props.BoolProperty(
        name="Set Scene Frame Length",
        description="Match the scene frame length with the frame length of the video.",
        default=True
    )

    bpy.types.Scene.option_tripod = bpy.props.BoolProperty(
        name="Tripod Mode (Rotation Only)",
        description="Were you using a tripod to shoot this video?",
        default=False,
        update=update_camera_parameters
    )

    bpy.types.Scene.finishing_up = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.at_is_finished = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.at_is_running = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.at_is_solving = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.resolve_buttonvisible = bpy.props.BoolProperty(default=False)

    bpy.types.Scene.option_customizeopticalcenter = bpy.props.BoolProperty(
        name="Customize Optical Center",
        description="Deviate Optical Center from using default settings",
        default=False
    )
    bpy.types.Scene.option_customizeradial = bpy.props.BoolProperty(
        name="Customize Radial Distortion",
        description="Deviate Radial Distortion from using default settings",
        default=False
    )

    bpy.types.Scene.collapse_markerplacement = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.collapse_solver = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.collapse_misc = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.collapse_objecttracking = bpy.props.BoolProperty(default=True)

    bpy.types.Scene.option_soundfinish = bpy.props.BoolProperty(
        default=True,
        name="Play Sound on Finish"
    )

    bpy.types.Scene.at_result_message = bpy.props.StringProperty(
        name="Result Message",
        default="Waiting for results..."
    )

    bpy.types.Scene.at_status_message = bpy.props.StringProperty(
        name="AutoTrack Status",
        default="AutoTrack hasn't started."
    )

    bpy.types.Scene.at_warning = bpy.props.StringProperty(
        name="AutoTrack Warning",
        default=""
    )

    bpy.types.Scene.at_remainingtime = bpy.props.StringProperty(
        name="Time Remaining",
        default="Time Remaining:"
    )

    bpy.types.Scene.at_progress = bpy.props.FloatProperty(
        name="Progress",
        default=0,
        min=0.0,
        max=100.0,
        subtype='PERCENTAGE'
    )

    bpy.types.Scene.at_about = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.at_processed_clips = bpy.props.StringProperty(default="")

    def execute(self, context):
        # function definitions

        def set_frame(frame):
            frame = int(math.ceil(frame))
            context.scene.frame_current = frame
            for space in area.spaces:
                if space.type == 'CLIP_EDITOR':
                    space.clip_user.frame_current = frame

        def refresh_screen():
            if scene.at_progress > 0:
                time_elapsed = time.time() - begin_time
                remaining_time = (time_elapsed / scene.at_progress) * (100 - scene.at_progress)
            else:
                remaining_time = 0
            mins, secs = divmod(int(remaining_time), 60)
            scene.at_remainingtime = f"Time Remaining: {mins:02d}:{secs:02d}"
            print(f"\nAUTOTRACK PROGRESS: {round(scene.at_progress, 2)}%. {scene.at_remainingtime}")

            try:
                with context.temp_override(window=context.window, area=area):
                    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                bpy.context.view_layer.update()
            except Exception as e:
                print(f"Could not refresh screen: {e}")

        def track_markers_sequence(backwards, start_frame, end_frame, progressincrease):
            set_frame(start_frame)
            computable_frames = math.fabs(start_frame - end_frame)
            print(f"Running tracking for {computable_frames} frames")
            count = start_frame

            for frame in range(int(math.fabs(start_frame - end_frame))):
                set_frame(count)
                if backwards:
                    count -= 1
                else:
                    count += 1

                if scene.frame_start <= count <= scene.frame_end:
                    refresh_screen()
                    time.sleep(0.05)
                    try:
                        bpy.ops.clip.track_markers(backwards=backwards, sequence=False)
                    except Exception as e:
                        print(f"Tracking for frame {count} failed: {e}")
                    time.sleep(0.05)
                scene.at_progress += progressincrease / computable_frames

        def count_alive_selected_trackers():
            active_obj = clip.tracking.objects.active
            if active_obj:
                tracks = active_obj.tracks
            else:
                tracks = clip.tracking.tracks

            alive_count = 0
            for track in tracks:
                if track.select:
                    marker = track.markers.find_frame(bpy.context.scene.frame_current)
                    if marker:
                        alive_count += 1
            return alive_count

        def play_finish_sound():
            try:
                device = aud.Device()
                addon_dir = Path(__file__).parent
                sound_path = addon_dir / "computing_finished.mp3"
                if sound_path.exists():
                    sound = aud.Sound(str(sound_path))
                    device.play(sound)
            except:
                print("There was a problem playing the finish sound.")

        def scan_markers(try_out=False):
            refresh_screen()
            if clip.size[0] > clip.size[1]:
                largest_side = clip.size[0]
            else:
                largest_side = clip.size[1]
            scale_factor = largest_side / 1920

            clip.tracking.settings.default_pattern_size = int((50 * scale_factor) * (scene.option_markerscale / 100))
            clip.tracking.settings.default_search_size = int((250 * scale_factor) * (scene.option_markerscale / 100))

            placement = 'FRAME'
            track_obj = clip.tracking.objects.active
            mapping = scene.at_object_mappings.get(track_obj.name) if track_obj else None
            use_ann = mapping.use_annotation if mapping else True
            ann_mode = mapping.annotation_mode if mapping else 'OPT1'

            try:
                temp_gp = None
                attr_name = "annotation" if hasattr(clip, "annotation") else "grease_pencil"
                original_gp = getattr(clip, attr_name, None)
                if use_ann:
                    source_gp = original_gp
                    if not source_gp:
                        source_gp = getattr(context.scene, attr_name, None)

                    if source_gp:
                        if ann_mode == "OPT1":
                            placement = 'OUTSIDE_GPENCIL'
                        else:
                            placement = 'INSIDE_GPENCIL'

                        temp_gp = source_gp.copy()
                        current_frame = scene.frame_current

                        for layer in temp_gp.layers:
                            valid_frame = None
                            for frame in layer.frames:
                                if frame.frame_number <= current_frame:
                                    if valid_frame is None or frame.frame_number > valid_frame.frame_number:
                                        valid_frame = frame
                            for frame in list(layer.frames):
                                if frame != valid_frame:
                                    layer.frames.remove(frame)
                        setattr(clip, attr_name, temp_gp)
            except:
                placement = 'FRAME'

            bpy.ops.clip.detect_features(margin=int((30 * scale_factor) * (scene.option_markerscale / 100)),
                                         placement=placement,
                                         threshold=scene.option_markerthreshold,
                                         min_distance=int((1.5 if try_out else 1) * (
                                                 (scale_factor) * context.scene.option_markerdistance)))
            try:
                setattr(clip, attr_name, original_gp)
                if temp_gp:
                    if hasattr(bpy.data, "annotations"):
                        bpy.data.annotations.remove(temp_gp)
                    else:
                        bpy.data.grease_pencils.remove(temp_gp)
            except:
                pass

        def get_solve_error():
            track_obj = clip.tracking.objects.active
            if track_obj:
                return track_obj.reconstruction.average_error
            return 0.0

        def get_reconstructed_count():
            track_obj = clip.tracking.objects.active
            if not track_obj: return 0.0
            total_tracks = len(track_obj.tracks)
            if total_tracks == 0: return 0.0
            reconstructed_count = 0
            for track in track_obj.tracks:
                if track.has_bundle:
                    reconstructed_count += 1
            return reconstructed_count / total_tracks

        def refine_solve(focal, radial):
            global refinement_solves

            prevprincipalpoint0 = prevprincipalpoint1 = 0
            prevradialk1 = prevradialk2 = prevradialk3 = 0

            clip.tracking.settings.use_keyframe_selection = False
            if not context.scene.option_customizeopticalcenter:
                clip.tracking.camera.principal_point[0] = 0
                clip.tracking.camera.principal_point[1] = 0
            if not context.scene.option_customizeradial:
                clip.tracking.camera.k1 = 0
                clip.tracking.camera.k2 = 0
                clip.tracking.camera.k3 = 0
            clip.tracking.camera.focal_length = scene.option_focallength
            refresh_screen()
            try:
                if context.scene.option_customizeopticalcenter:
                    prevprincipalpoint0 = clip.tracking.camera.principal_point[0]
                    prevprincipalpoint1 = clip.tracking.camera.principal_point[1]
                if context.scene.option_customizeradial:
                    prevradialk1 = clip.tracking.camera.k1
                    prevradialk2 = clip.tracking.camera.k2
                    prevradialk3 = clip.tracking.camera.k3
                clip.tracking.settings.refine_intrinsics_focal_length = focal
                clip.tracking.settings.refine_intrinsics_radial_distortion = radial
                scene.at_progress += 10 / 3
                bpy.ops.clip.solve_camera()
                solve_error = get_solve_error()
                track_reconstruction = get_reconstructed_count()

                if context.scene.option_customizeopticalcenter:
                    clip.tracking.camera.principal_point[0] = prevprincipalpoint0
                    clip.tracking.camera.principal_point[1] = prevprincipalpoint1
                if context.scene.option_customizeradial:
                    clip.tracking.camera.k1 = prevradialk1
                    clip.tracking.camera.k2 = prevradialk2
                    clip.tracking.camera.k3 = prevradialk3

                print(f"RESULT OF {focal} {radial} : {solve_error}")
                return ([solve_error, track_reconstruction, focal, radial])
            except Exception as e:
                print(e)

        def get_failed_reconstruction_frame_count(clip, threshold=4):
            if not clip:
                return 0

            failed_frames = 0
            start_frame = context.scene.frame_start
            end_frame = context.scene.frame_end
            track_obj = clip.tracking.objects.active
            for f in range(start_frame, end_frame + 1):
                valid_bundles_on_frame = 0
                for track in track_obj.tracks:
                    if track.has_bundle:
                        if track.markers.find_frame(f):
                            valid_bundles_on_frame += 1
                if valid_bundles_on_frame < threshold:
                    failed_frames += 1
            return failed_frames

        def obtain_percentile_of_trackers(value):
            track_obj = clip.tracking.objects.active
            data = tuple(t.average_error for t in track_obj.tracks)
            sorted_data = sorted(data)
            n = len(sorted_data)
            if n == 0: return 0.0
            index = (value / 100) * (n - 1)
            lower_index = int(index)
            fraction = index - lower_index
            if lower_index + 1 >= n:
                q3 = sorted_data[lower_index]
            else:
                lower_value = sorted_data[lower_index]
                upper_value = sorted_data[lower_index + 1]
                q3 = lower_value + (upper_value - lower_value) * fraction
            print(f"{q3} is the 75th percentile!")
            return q3

        def best_current_solve(current_keyframe_solves):
            try:
                if not len(current_keyframe_solves) == 0:
                    top_current_amount = int(len(current_keyframe_solves) / 2)
                    top_current_reprojection = sorted(current_keyframe_solves, key=lambda x: x[3], reverse=True)[
                        :top_current_amount]
                    best_current_solve = min(range(len(top_current_reprojection)),
                                             key=lambda i: top_current_reprojection[i][2])
                    context.scene.at_bestsolve = f"Current Best Solve: {round(top_current_reprojection[best_current_solve][2], 2)}px {round(top_current_reprojection[best_current_solve][3], 2) * 100}%"
                    if not top_current_reprojection[best_current_solve][4] == 0:
                        scene.at_warning = f"Solve got {top_current_reprojection[best_current_solve][4]} missing frames."
                    else:
                        scene.at_warning = ""
            except Exception as e:
                print(e)

        def best_current_refine_solve(current_refine_solves):
            try:
                if not len(current_refine_solves) == 0:
                    best_current_solve = min(range(len(current_refine_solves)),
                                             key=lambda i: current_refine_solves[i][0])
                    context.scene.at_bestsolve = f"Current Best Solve: {round(current_refine_solves[best_current_solve][0], 2)}px"
            except Exception as e:
                print(e)

        def solve_camera(iterations, initialsolve=False, cleanupsolve=False):
            scene.finishing_up = False
            clip.tracking.settings.use_keyframe_selection = False
            clip.tracking.settings.refine_intrinsics_focal_length = False
            clip.tracking.settings.refine_intrinsics_principal_point = False
            clip.tracking.settings.refine_intrinsics_radial_distortion = False
            context.scene.at_is_solving = True

            track_obj = clip.tracking.objects.active
            is_camera = track_obj.is_camera

            # 1. Always ensure a camera exists in the scene
            if not bpy.context.scene.camera:
                cam_data = bpy.data.cameras.new(name="Camera")
                cam = bpy.data.objects.new(name="Camera", object_data=cam_data)
                bpy.context.scene.collection.objects.link(cam)
                bpy.context.scene.camera = cam
                cam.location = (0, 0, 0)
                cam.rotation_euler = (1.5708, 0, 1.5708)

            cam = bpy.context.scene.camera

            # 2. Always ensure a Camera Solver constraint exists and links to the clip
            # (This forces Blender's 3D viewport to display the tracking markers/bundles)
            solver_c = next((c for c in cam.constraints if c.type == 'CAMERA_SOLVER'), None)
            if not solver_c:
                try:
                    solver_c = cam.constraints.new(type='CAMERA_SOLVER')
                except Exception as e:
                    print(e)
            if solver_c:
                solver_c.clip = clip

            # 3. Only reset initial position/rotation if we are solving a moving camera
            if is_camera:
                cam.rotation_euler[0] = 1.5708
                cam.rotation_euler[1] = 0
                cam.rotation_euler[2] = 1.5708
                cam.location[0] = 10
                cam.location[1] = 0
                cam.location[2] = 0

            keyframe_solves = []
            attempts = iterations
            if initialsolve:
                context.scene.at_status_message = f"Performing solves... (1/{attempts})"
            else:
                context.scene.at_status_message = f"Performing final solves... (1/{attempts})"

            context.scene.at_bestsolve = f"No solve has been made yet"
            refresh_screen()
            errorcount = 0
            scene.at_warning = ""
            while len(keyframe_solves) < attempts and errorcount < 1000:
                keyframe_a = random.randint(start_frame, end_frame)
                keyframe_b = random.randint(start_frame, end_frame)
                track_obj.keyframe_a = keyframe_a
                track_obj.keyframe_b = keyframe_b
                try:
                    bpy.ops.clip.solve_camera()
                    solve_error = get_solve_error()
                    track_reconstruction = get_reconstructed_count()

                    try:
                        failed_frames = get_failed_reconstruction_frame_count(clip)
                    except Exception as e:
                        print(e)
                        failed_frames = 0

                    keyframe_solves.append([keyframe_a, keyframe_b, solve_error, track_reconstruction, failed_frames])
                    best_current_solve(keyframe_solves)
                    refresh_screen()

                    if cleanupsolve:
                        if (scene.option_refinefocallength or scene.option_refinedistortion) and is_camera:
                            scene.at_progress += 10 / attempts
                        else:
                            scene.at_progress += 15 / attempts
                    else:
                        if (scene.option_refinefocallength or scene.option_refinedistortion) and is_camera:
                            scene.at_progress += 20 / attempts
                        else:
                            scene.at_progress += 30 / attempts

                    if initialsolve:
                        context.scene.at_status_message = f"Performing solves... ({len(keyframe_solves) + 1}/{attempts})"
                    else:
                        context.scene.at_status_message = f"Performing final solves... ({len(keyframe_solves) + 1}/{attempts})"
                except Exception as e:
                    print(f"This solve failed. Retrying, this is retry nr. {errorcount}/1000. {e}")
                    errorcount += 1

            if len(keyframe_solves) > 0:
                top_amount = int(len(keyframe_solves) / 2)
                top_reprojection = sorted(keyframe_solves, key=lambda x: x[3], reverse=True)[:top_amount]
                best_solve = min(range(len(top_reprojection)), key=lambda i: top_reprojection[i][2])

                track_obj.keyframe_a = top_reprojection[best_solve][0]
                track_obj.keyframe_b = top_reprojection[best_solve][1]

                allow_refine = (scene.option_refinefocallength or scene.option_refinedistortion) if is_camera else False

                if ((not initialsolve) or (top_reprojection[best_solve][2]) < 1 * scale_factor) and allow_refine:
                    global refinement_solves
                    scene.finishing_up = True
                    scene.at_progress = 90
                    refinement_solves = []
                    refinement_solves.append(
                        [top_reprojection[best_solve][2], top_reprojection[best_solve][3], False, False])
                    best_current_refine_solve(refinement_solves)

                    if scene.option_refinefocallength:
                        context.scene.at_status_message = f"Refining Solve... (1/3)"
                        refresh_screen()
                        refinement_solves.append(refine_solve(True, False))
                        best_current_refine_solve(refinement_solves)

                    if scene.option_refinedistortion:
                        context.scene.at_status_message = f"Refining Solve... (2/3)"
                        refresh_screen()
                        refinement_solves.append(refine_solve(False, True))
                        best_current_refine_solve(refinement_solves)

                    if scene.option_refinefocallength and scene.option_refinedistortion:
                        context.scene.at_status_message = f"Refining Solve... (3/3)"
                        refresh_screen()
                        refinement_solves.append(refine_solve(True, True))
                        best_current_refine_solve(refinement_solves)

                    refresh_screen()

                    if not len(refinement_solves) == 0:
                        best_solve_refine = min(range(len(refinement_solves)), key=lambda i: refinement_solves[i][0])
                        clip.tracking.settings.refine_intrinsics_focal_length = refinement_solves[best_solve_refine][2]
                        clip.tracking.settings.refine_intrinsics_radial_distortion = \
                            refinement_solves[best_solve_refine][3]
                    else:
                        print("There are no refinements")

                if is_camera:
                    if not context.scene.option_customizeopticalcenter:
                        clip.tracking.camera.principal_point[0] = 0
                        clip.tracking.camera.principal_point[1] = 0
                    if not context.scene.option_customizeradial:
                        clip.tracking.camera.k1 = 0
                        clip.tracking.camera.k2 = 0
                        clip.tracking.camera.k3 = 0
                    clip.tracking.camera.focal_length = scene.option_focallength

                if scene.finishing_up:
                    scene.at_progress = 100
                    context.scene.at_status_message = f"Applying Best Solve..."
                    refresh_screen()

                bpy.ops.clip.solve_camera()

                if scene.finishing_up:
                    context.scene.at_is_solving = False

                context.scene.at_result_message = f"Finished: {round(get_solve_error(), 2)}px and {round(get_reconstructed_count(), 2) * 100}% reconstructed markers."
            else:
                self.report({'WARNING'}, "Solving failed, no solutions were found. Try tracking with more markers.")
                scene.at_result_message = f"Solving failed, no solutions found."
                context.scene.at_is_running = True
                context.scene.at_is_finished = False
                return {'CANCELLED'}

        def kill_all_markers():
            bpy.context.space_data.show_disabled = True
            bpy.ops.clip.select_all(action='SELECT')
            bpy.ops.clip.delete_track()
            bpy.context.space_data.show_disabled = False

        def kill_timeline_markers():
            scene = bpy.context.scene
            markers_to_delete = []

            for marker in scene.timeline_markers:
                if marker.name.startswith("AutoTrack"):
                    markers_to_delete.append(marker)
            for marker in markers_to_delete:
                scene.timeline_markers.remove(marker)

        def enough_markers_left(min_count=16, include_selected=True):
            try:
                frame_counts = {f: 0 for f in range(start_frame, end_frame + 1)}
                track_obj = clip.tracking.objects.active

                for track in track_obj.tracks:
                    if not include_selected and track.select:
                        continue
                    for marker in track.markers:
                        if not marker.mute and marker.frame in frame_counts:
                            frame_counts[marker.frame] += 1

                for frame, count in frame_counts.items():
                    if count < min_count:
                        print(f"Frame {frame} failed: Has {count} markers (Needed {min_count})")
                        return False
                return True
            except Exception as e:
                print(f"Error in enough_markers_left: {e}")
                return False

        def deselect_disabled_markers():
            track_obj = clip.tracking.objects.active
            for track in track_obj.tracks:
                if track.select:
                    marker = track.markers.find_frame(scene.frame_current)
                    if marker is None or marker.mute:
                        track.select = False

        def change_filter_threshold(value, upwards, globalfilter):
            global track_threshold
            if upwards:
                track_threshold += value
            else:
                track_threshold -= value
            bpy.ops.clip.filter_tracks(track_threshold=track_threshold)
            if not globalfilter:
                deselect_disabled_markers()
            refresh_screen()

        context.scene.at_status_message = "Setting up parameters..."

        clip = context.edit_movieclip
        bpy.context.space_data.mode = 'TRACKING'
        scene = bpy.context.scene
        area = context.area
        scene.at_progress = 0

        if not clip:
            self.report({'WARNING'}, "No video clip is selected")
            return {'CANCELLED'}


        if scene.option_setsceneframe:
            bpy.ops.clip.set_scene_frames()
        else:
            if scene.frame_end > clip.frame_duration:
                scene.frame_end = clip.frame_duration
                self.report({'WARNING'}, "Corrected scene end frame because your video is shorter than your timeline.")
            if scene.frame_start < 1:
                scene.frame_start = 1
                self.report({'WARNING'}, "Corrected scene begin frame because it was below 1.")

        start_frame = scene.frame_start
        end_frame = scene.frame_end

        if scene.frame_step != 1:
            self.report({'ERROR'}, f"Tracking failed! Scene Frame Step must be 1 to be able to track.")
            return {'CANCELLED'}

        try:
            global begin_time
            begin_time = time.time()
            total_frames = end_frame - start_frame
            clip.tracking.settings.use_tripod_solver = scene.option_tripod

            if not context.scene.option_customizeopticalcenter:
                clip.tracking.camera.principal_point[0] = 0
                clip.tracking.camera.principal_point[1] = 0
            if not context.scene.option_customizeradial:
                clip.tracking.camera.k1 = 0
                clip.tracking.camera.k2 = 0
                clip.tracking.camera.k3 = 0

            clip.tracking.camera.focal_length = scene.option_focallength

            context.scene.at_is_running = True
            context.scene.at_is_finished = False
            context.scene.at_is_solving = False
            clip.tracking.settings.default_motion_model = 'Loc'
            clip.tracking.settings.default_pattern_match = 'KEYFRAME'
            clip.tracking.settings.use_default_normalization = True
            bpy.context.space_data.show_disabled = True

            set_frame(start_frame)
            bpy.ops.clip.select_all(action='SELECT')
            bpy.ops.clip.delete_track()
            kill_timeline_markers()

            bpy.context.space_data.show_disabled = False
            frame = start_frame
            substep_frames = []
            context.scene.at_status_message = f"Searching Substeps... (0/{int(total_frames / scene.option_marker_frame_interval)})"
            refresh_screen()
            scan_markers(True)
            marker_threshold = count_alive_selected_trackers()
            max_substep_length = scene.option_marker_frame_interval

            try:
                substep_frames.append([start_frame, 0, scene.option_min_track_length])
                while frame < end_frame:
                    running_frames = 0
                    while True:
                        running_frames += 1
                        bpy.ops.clip.track_markers(backwards=False, sequence=False)
                        frame += 1
                        scene.at_progress += (10 / (end_frame - start_frame))
                        set_frame(frame)
                        alive_markers = count_alive_selected_trackers()
                        if alive_markers < marker_threshold / (1 / (
                                scene.option_markers_retention / 100)) or frame > end_frame or running_frames >= max_substep_length:
                            break
                    if not frame > end_frame:
                        kill_all_markers()
                        context.scene.at_status_message = f"Searching Substeps... ({int((frame - start_frame) / scene.option_marker_frame_interval)}/{int(total_frames / scene.option_marker_frame_interval)})"
                        refresh_screen()
                        scan_markers(True)
                        try:
                            substep_frames[-1][2] = running_frames
                        except:
                            pass
                        substep_frames.append([frame, running_frames, scene.option_min_track_length])
                        context.scene.timeline_markers.new(name=f"AutoTrack Substep {len(substep_frames)}", frame=frame)
                        bpy.ops.clip.select_all(action='SELECT')
                        marker_threshold = count_alive_selected_trackers()
            except Exception as e:
                print(e)

            substep_frames.append([end_frame, scene.option_min_track_length, 0])
            kill_all_markers()
            set_frame(start_frame)
            scene.at_progress = 10
            least_amount_of_markers = 999999999999

            for index, frame in enumerate(substep_frames):
                set_frame(frame[0])
                scan_markers()
                markers_amount = count_alive_selected_trackers()

                if markers_amount < least_amount_of_markers:
                    least_amount_of_markers = markers_amount

                context.scene.at_status_message = f"Substep Forwards Tracking... ({index + 1}/{len(substep_frames)})"
                track_markers_sequence(False, frame[0], frame[0] + max((scene.option_min_track_length // 2), frame[2]),
                                       20 / len(substep_frames))
                context.scene.at_status_message = f"Substep Backwards Tracking... ({index + 1}/{len(substep_frames)})"
                track_markers_sequence(True, frame[0], frame[0] - max((scene.option_min_track_length // 2), frame[1]),
                                       20 / len(substep_frames))

            if scene.option_tracks_prefiltering_perc >= scene.option_tracks_cleanup_perc:
                min_tracks_prefiltering = int((least_amount_of_markers * (
                        scene.option_tracks_prefiltering_perc / 100)) if least_amount_of_markers > 25 else 20)
                min_tracks_cleanup = int((least_amount_of_markers * (
                        scene.option_tracks_cleanup_perc / 100)) if least_amount_of_markers > 25 else 15)
            else:
                min_tracks_prefiltering = int((least_amount_of_markers * (0.8)) if least_amount_of_markers > 25 else 20)
                min_tracks_cleanup = int((least_amount_of_markers * (0.6)) if least_amount_of_markers > 25 else 15)

                # --- NEW OVERRIDE FOR OBJECT TRACKING ---
            active_track_obj = clip.tracking.objects.active
            if active_track_obj and not active_track_obj.is_camera:
                # override default logic when Object Tracking
                min_tracks_prefiltering = int(8 + max(0, least_amount_of_markers - 8) / 2)
                min_tracks_cleanup = 8
            # ----------------------------------------

            scene.at_progress = 50
            bpy.ops.clip.select_all(action='DESELECT')
            minimum_tracks = min_tracks_prefiltering

            if (not context.scene.option_filterpasses == "OPT1") and (enough_markers_left(minimum_tracks, True)):
                global track_threshold
                track_threshold = 50
                bpy.context.space_data.show_disabled = True
                scene.at_status_message = f"Running global filter... "
                refresh_screen()
                change_filter_threshold(0, False, True)
                while enough_markers_left(minimum_tracks, False) and track_threshold > 15:
                    change_filter_threshold(3, False, True)

                if not enough_markers_left(minimum_tracks, False):
                    while not enough_markers_left(minimum_tracks, False):
                        change_filter_threshold(1, True, True)

                if not enough_markers_left(minimum_tracks, False):
                    print(
                        f"SOMETHING WENT WRONG WITH DELETION. global filter at threshold {track_threshold}. Won't delete tracks.")
                else:
                    bpy.ops.clip.delete_track()

                scene.at_status_message = f"Prefiltering Tracks... (0/{len(substep_frames)})"
                refresh_screen()
                bpy.context.space_data.show_disabled = False
                if enough_markers_left(minimum_tracks, True):
                    for index, frame in enumerate(substep_frames):
                        set_frame(frame[0])
                        scene.at_status_message = f"Prefiltering Tracks... ({index + 1}/{len(substep_frames)})"
                        scene.at_progress += (20 / len(substep_frames))
                        refresh_screen()

                        change_filter_threshold(0, False, False)
                        if enough_markers_left(minimum_tracks, False) and track_threshold > 15:
                            while enough_markers_left(minimum_tracks, False) and track_threshold > 15:
                                change_filter_threshold(1, False, False)

                        if not enough_markers_left(minimum_tracks, False):
                            while not enough_markers_left(minimum_tracks, False):
                                change_filter_threshold(1, True, False)

                        if not enough_markers_left(minimum_tracks, False):
                            print(
                                f"SOMETHING WENT WRONG WITH DELETION. frame {frame[0]} at threshold {track_threshold}. Won't delete tracks.")
                        else:
                            bpy.ops.clip.delete_track()
                else:
                    print("Not enough markers to start filtering. This should not happen and should be reported.")
            else:
                scene.at_status_message = f"Filtering Tracks..."
                refresh_screen()
                bpy.context.space_data.show_disabled = True
                bpy.ops.clip.filter_tracks(track_threshold=20)
                bpy.ops.clip.delete_track()
                bpy.context.space_data.show_disabled = False
                refresh_screen()

            scene.at_progress = 70
            clip.tracking.camera.focal_length = scene.option_focallength
            refresh_screen()

        except Exception as e:
            self.report({'ERROR'}, f"Tracking failed! {e}")
            scene.at_result_message = f"Tracking failed to complete."
            scene.at_is_running = False
            scene.at_is_finished = True
            return {'CANCELLED'}

        try:
            if clip.size[0] > clip.size[1]:
                largest_side = clip.size[0]
            else:
                largest_side = clip.size[1]
            scale_factor = largest_side / 1920
            minimum_tracks = min_tracks_cleanup

            if ((not scene.option_tripod) and (scene.option_filterpasses == 'OPT3')) and enough_markers_left(
                    minimum_tracks, True):
                solve_camera(scene.option_solveriterations, True, True)
                if not scene.finishing_up:
                    percentile_detect = 100
                    bpy.context.space_data.show_disabled = True
                    bpy.ops.clip.select_all(action='DESELECT')
                    bpy.ops.clip.clean_tracks(frames=0, error=obtain_percentile_of_trackers(percentile_detect),
                                              action='SELECT')
                    refresh_screen()
                    while enough_markers_left(minimum_tracks, False) and percentile_detect > 80:
                        percentile_detect -= 3
                        scene.at_status_message = f"Cleaning Tracks... ({percentile_detect}th %)"
                        bpy.ops.clip.clean_tracks(frames=0, error=obtain_percentile_of_trackers(percentile_detect),
                                                  action='SELECT')
                        refresh_screen()
                        if (not enough_markers_left(minimum_tracks, False)) or percentile_detect < 80:
                            percentile_detect += 1
                            break
                    bpy.ops.clip.clean_tracks(frames=0, error=obtain_percentile_of_trackers(percentile_detect),
                                              action='DELETE_TRACK')
                    bpy.ops.clip.delete_track()
                    bpy.context.space_data.show_disabled = False

                    solve_camera(scene.option_solveriterations, False, True)
                else:
                    pass
            else:
                refresh_screen()
                if scene.option_tripod:
                    solve_camera(2, False, False)
                else:
                    solve_camera(scene.option_solveriterations, False, False)

                context.scene.at_result_message = f"Finished: {round(get_solve_error(), 2)}px and {round(get_reconstructed_count(), 2) * 100}% reconstructed markers."

            try:
                # Always apply resolution, lens, and set background video on camera
                cam = bpy.context.scene.camera
                if cam:
                    cam.data.lens = clip.tracking.camera.focal_length
                    cam.data.sensor_width = clip.tracking.camera.sensor_width
                    context.scene.render.resolution_x = clip.size[0]
                    context.scene.render.resolution_y = clip.size[1]
                    bpy.ops.clip.set_viewport_background()

                if clip.tracking.objects.active.is_camera:
                    scene.option_focallength = clip.tracking.camera.focal_length
            except Exception as e:
                print(e)

            scene.resolve_buttonvisible = False
            self.report({'INFO'}, context.scene.at_result_message)

        except Exception as e:
            self.report({'ERROR'}, f"Solving failed! {e}")
            scene.at_result_message = f"Solving failed to complete."
            scene.at_is_running = False
            scene.at_is_finished = True
            return {'CANCELLED'}

        scene.at_is_running = False
        scene.at_is_finished = True

        if scene.option_soundfinish:
            play_finish_sound()
        return {'FINISHED'}


# class for the quick resolve button / operator
class QuickResolve(bpy.types.Operator):
    bl_idname = "autotrack.quickresolve"
    bl_label = "Quick Resolve"
    bl_description = "Run the solver without re-tracking"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        clip = context.edit_movieclip
        clip.tracking.settings.use_tripod_solver = context.scene.option_tripod
        context.scene.resolve_buttonvisible = False

        if not clip:
            self.report({'ERROR'}, "No clip selected")
            return {'CANCELLED'}
        try:
            bpy.ops.clip.solve_camera()
            if clip.tracking.objects.active.is_camera:
                context.scene.option_focallength = clip.tracking.camera.focal_length
        except Exception as e:
            self.report({'ERROR'}, f"Quick Resolve failed: {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Quick Resolve completed! Please re-run for a more accurate result.")
        return {'FINISHED'}


# class for the test markers button / operator
class TestMarkers(bpy.types.Operator):
    bl_idname = "autotrack.testmarkers"
    bl_label = "Test Markers"
    bl_description = "Test the placement of markers on the current frame"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        clip = context.edit_movieclip
        if clip:
            try:
                scene = context.scene
                bpy.context.space_data.show_disabled = True
                bpy.ops.clip.select_all(action='SELECT')
                bpy.ops.clip.delete_track()
                bpy.context.space_data.show_disabled = False

                if clip.size[0] > clip.size[1]:
                    largest_side = clip.size[0]
                else:
                    largest_side = clip.size[1]
                scale_factor = largest_side / 1920

                clip.tracking.settings.default_pattern_size = int(
                    (50 * scale_factor) * (scene.option_markerscale / 100))
                clip.tracking.settings.default_search_size = int(
                    (250 * scale_factor) * (scene.option_markerscale / 100))

                placement = 'FRAME'

                track_obj = clip.tracking.objects.active
                mapping = scene.at_object_mappings.get(track_obj.name) if track_obj else None
                use_ann = mapping.use_annotation if mapping else True
                ann_mode = mapping.annotation_mode if mapping else 'OPT1'

                try:
                    temp_gp = None
                    attr_name = "annotation" if hasattr(clip, "annotation") else "grease_pencil"
                    original_gp = getattr(clip, attr_name, None)
                    if use_ann:
                        source_gp = original_gp
                        if not source_gp:
                            source_gp = getattr(context.scene, attr_name, None)

                        if source_gp:
                            if ann_mode == "OPT1":
                                placement = 'OUTSIDE_GPENCIL'
                            else:
                                placement = 'INSIDE_GPENCIL'

                            temp_gp = source_gp.copy()
                            current_frame = scene.frame_current
                            for layer in temp_gp.layers:
                                valid_frame = None
                                for frame in layer.frames:
                                    if frame.frame_number <= current_frame:
                                        if valid_frame is None or frame.frame_number > valid_frame.frame_number:
                                            valid_frame = frame
                                for frame in list(layer.frames):
                                    if frame != valid_frame:
                                        layer.frames.remove(frame)
                            setattr(clip, attr_name, temp_gp)
                except:
                    placement = 'FRAME'

                bpy.ops.clip.detect_features(margin=int((30 * scale_factor) * (scene.option_markerscale / 100)),
                                             placement=placement,
                                             threshold=context.scene.option_markerthreshold,
                                             min_distance=int(((scale_factor) * context.scene.option_markerdistance)))

                try:
                    setattr(clip, attr_name, original_gp)
                    if temp_gp:
                        if hasattr(bpy.data, "annotations"):
                            bpy.data.annotations.remove(temp_gp)
                        else:
                            bpy.data.grease_pencils.remove(temp_gp)
                except:
                    pass

                self.report({'INFO'}, f"Placed markers!")
                return {'FINISHED'}
            except Exception as e:
                self.report({'ERROR'}, f"Placing markers caused an error: {e}")
                return {'CANCELLED'}
        else:
            self.report({'WARNING'}, "No video clip is selected")
            return {'CANCELLED'}


class ClearGreasePencil(bpy.types.Operator):
    bl_idname = "autotrack.cleargreasepencil"
    bl_label = "Clear Annotations"
    bl_description = "Clears annotations on current video"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if hasattr(bpy.data, "annotations"):
            attr_name = "annotation"
            data_storage = bpy.data.annotations
        else:
            attr_name = "grease_pencil"
            data_storage = bpy.data.grease_pencils

        objects_to_check = list(bpy.data.movieclips)
        objects_to_check.append(context.scene)

        items_to_delete = set()
        for obj in objects_to_check:
            data = getattr(obj, attr_name, None)
            if data:
                items_to_delete.add(data)
                setattr(obj, attr_name, None)

        count = 0
        for item in items_to_delete:
            try:
                data_storage.remove(item)
                count += 1
            except:
                pass

        self.report({'INFO'}, f"Deleted annotations from {count} sources")
        return {'FINISHED'}


class GenerateSurface(bpy.types.Operator):
    bl_idname = "autotrack.generatesurface"
    bl_label = "Generate Surface (Beta)"
    bl_description = "Generates a Surface with reprojection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            def apply_camera_projection(mesh_obj):
                scene = bpy.context.scene
                camera = scene.camera
                if not camera: return
                if not mesh_obj.data.uv_layers:
                    mesh_obj.data.uv_layers.new(name="Projected_UV")
                mod = mesh_obj.modifiers.new(name="Camera_Projection", type='UV_PROJECT')
                mod.projectors[0].object = camera
                mod.uv_layer = mesh_obj.data.uv_layers[0].name
                res_x = scene.render.resolution_x
                res_y = scene.render.resolution_y
                if res_y > 0:
                    mod.aspect_x = res_x
                    mod.aspect_y = res_y

            def get_active_movie_clip():
                if getattr(bpy.context, "edit_movieclip", None):
                    return bpy.context.edit_movieclip
                for area in bpy.context.screen.areas:
                    if area.type == 'CLIP_EDITOR':
                        space = area.spaces.active
                        if space and space.clip:
                            return space.clip
                return None

            clip = get_active_movie_clip()
            if not clip: return {'CANCELLED'}
            track_obj = clip.tracking.objects.active
            if not track_obj: return {'CANCELLED'}
            track_obj_name = track_obj.name

            # Dynamically set the naming convention
            base_name = "Environment_PointCloudSurface" if track_obj_name == "Camera" else f"{track_obj_name}_PointCloudSurface"

            def apply_active_clip_material(obj):
                if not clip: return None
                mat_name = f"Mat_{clip.name}"
                mat = bpy.data.materials.get(mat_name)
                if not mat:
                    mat = bpy.data.materials.new(name=mat_name)

                mat.use_nodes = True
                nodes = mat.node_tree.nodes
                links = mat.node_tree.links
                nodes.clear()
                node_out = nodes.new('ShaderNodeOutputMaterial')
                node_out.location = (400, 0)
                node_emit = nodes.new('ShaderNodeEmission')
                node_emit.location = (200, 0)
                node_tex = nodes.new('ShaderNodeTexImage')
                node_tex.location = (-100, 0)
                node_tex.label = clip.name

                image_block = None
                for img in bpy.data.images:
                    if img.filepath == clip.filepath:
                        image_block = img
                        break
                if not image_block:
                    try:
                        image_block = bpy.data.images.load(clip.filepath)
                    except RuntimeError:
                        return mat
                node_tex.image = image_block
                node_tex.image_user.use_auto_refresh = True
                node_tex.image_user.frame_duration = clip.frame_duration
                node_tex.image_user.frame_start = clip.frame_start
                node_tex.image_user.frame_offset = clip.frame_offset
                node_tex.extension = 'EXTEND'
                node_uv = nodes.new('ShaderNodeUVMap')
                node_uv.location = (-300, 0)
                node_uv.uv_map = "Projected_UV"
                links.new(node_uv.outputs['UV'], node_tex.inputs['Vector'])
                links.new(node_tex.outputs['Color'], node_emit.inputs['Color'])
                links.new(node_emit.outputs['Emission'], node_out.inputs['Surface'])

                if obj.data.materials:
                    obj.data.materials[0] = mat
                else:
                    obj.data.materials.append(mat)
                return mat

            def create_tracks_node_tree(obj, applied_material):
                modifier_name = "Surface Generator"
                mod = obj.modifiers.get(modifier_name)
                if not mod:
                    mod = obj.modifiers.new(name=modifier_name, type='NODES')
                tree_name = "SurfaceGenerator_Nodes"
                if mod.node_group:
                    bpy.data.node_groups.remove(mod.node_group)
                node_tree = bpy.data.node_groups.new(name=tree_name, type='GeometryNodeTree')
                nodes = node_tree.nodes
                links = node_tree.links
                for item in list(node_tree.interface.items_tree):
                    node_tree.interface.remove(item)

                in_geo = node_tree.interface.new_socket(name="Geometry", in_out='INPUT',
                                                        socket_type='NodeSocketGeometry')
                in_res = node_tree.interface.new_socket(name="Resolution", in_out='INPUT', socket_type='NodeSocketInt')
                in_res.default_value = 300
                in_res.min_value = 1
                in_rad = node_tree.interface.new_socket(name="Connection Radius", in_out='INPUT',
                                                        socket_type='NodeSocketFloat')
                in_rad.default_value = 0.2
                in_rad.min_value = 0.0

                out_geo = node_tree.interface.new_socket(name="Geometry", in_out='OUTPUT',
                                                         socket_type='NodeSocketGeometry')

                n_input = nodes.new('NodeGroupInput')
                n_input.location = (-900, 0)
                n_output = nodes.new('NodeGroupOutput')
                n_output.location = (1400, 0)
                n_position = nodes.new('GeometryNodeInputPosition')
                n_position.location = (-900, 200)
                n_length = nodes.new('ShaderNodeVectorMath')
                n_length.location = (-700, 200)
                n_length.operation = 'LENGTH'
                n_compare = nodes.new('FunctionNodeCompare')
                n_compare.location = (-500, 200)
                n_compare.operation = 'GREATER_THAN'
                n_compare.data_type = 'FLOAT'
                n_compare.inputs[1].default_value = 100.00
                n_del_geo = nodes.new('GeometryNodeDeleteGeometry')
                n_del_geo.location = (-500, 0)
                n_del_geo.domain = 'POINT'

                n_mesh_to_pts = nodes.new('GeometryNodeMeshToPoints')
                n_mesh_to_pts.location = (-400, 100)
                n_pts_to_vol = nodes.new('GeometryNodePointsToVolume')
                n_pts_to_vol.location = (-300, 100)
                if hasattr(n_pts_to_vol, 'resolution_mode'):
                    n_pts_to_vol.resolution_mode = 'VOXEL_AMOUNT'
                if 'Density' in n_pts_to_vol.inputs:
                    n_pts_to_vol.inputs['Density'].default_value = 3.4

                n_vol_to_mesh = nodes.new('GeometryNodeVolumeToMesh')
                n_vol_to_mesh.location = (-100, 200)
                if hasattr(n_vol_to_mesh, 'resolution_mode'):
                    n_vol_to_mesh.resolution_mode = 'GRID'
                if 'Threshold' in n_vol_to_mesh.inputs:
                    n_vol_to_mesh.inputs['Threshold'].default_value = 0.1
                if 'Adaptivity' in n_vol_to_mesh.inputs:
                    n_vol_to_mesh.inputs['Adaptivity'].default_value = 0.0

                n_realize = nodes.new('GeometryNodeRealizeInstances')
                n_realize.location = (100, 200)
                n_proximity = nodes.new('GeometryNodeProximity')
                n_proximity.location = (-100, -100)
                n_proximity.target_element = 'POINTS'
                n_set_pos = nodes.new('GeometryNodeSetPosition')
                n_set_pos.location = (300, 0)
                n_set_mat = nodes.new('GeometryNodeSetMaterial')
                n_set_mat.location = (500, 0)
                if applied_material:
                    n_set_mat.inputs[2].default_value = applied_material
                n_merge = nodes.new('GeometryNodeMergeByDistance')
                n_merge.location = (700, 0)
                if hasattr(n_merge, 'mode'):
                    n_merge.mode = 'ALL'
                n_merge.inputs['Distance'].default_value = 0.001

                links.new(n_position.outputs['Position'], n_length.inputs['Vector'])
                links.new(n_length.outputs['Value'], n_compare.inputs['A'])
                links.new(n_compare.outputs['Result'], n_del_geo.inputs['Selection'])
                links.new(n_input.outputs['Geometry'], n_del_geo.inputs['Geometry'])
                links.new(n_del_geo.outputs['Geometry'], n_mesh_to_pts.inputs['Mesh'])
                links.new(n_mesh_to_pts.outputs['Points'], n_pts_to_vol.inputs['Points'])
                links.new(n_input.outputs['Resolution'], n_pts_to_vol.inputs['Voxel Amount'])
                links.new(n_input.outputs['Connection Radius'], n_pts_to_vol.inputs['Radius'])
                links.new(n_pts_to_vol.outputs['Volume'], n_vol_to_mesh.inputs['Volume'])
                links.new(n_vol_to_mesh.outputs['Mesh'], n_realize.inputs['Geometry'])
                links.new(n_realize.outputs['Geometry'], n_set_pos.inputs['Geometry'])
                links.new(n_del_geo.outputs['Geometry'], n_proximity.inputs['Target'])
                links.new(n_proximity.outputs['Position'], n_set_pos.inputs['Position'])
                links.new(n_set_pos.outputs['Geometry'], n_set_mat.inputs['Geometry'])
                links.new(n_set_mat.outputs['Geometry'], n_merge.inputs['Geometry'])
                links.new(n_merge.outputs['Geometry'], n_output.inputs['Geometry'])

                mod.node_group = node_tree

            def delete_old_track_object(b_name):
                current_scene = bpy.context.scene
                objs_to_delete = [obj for obj in current_scene.objects if
                                  obj.name == b_name or obj.name.startswith(b_name + ".")]
                for obj in objs_to_delete:
                    bpy.data.objects.remove(obj, do_unlink=True)

            def create_pointcloud():
                bpy.context.space_data.show_disabled = True
                bpy.ops.clip.select_all(action='SELECT')
                bpy.ops.clip.bundles_to_mesh()
                bpy.context.space_data.show_disabled = False
                return bpy.context.active_object

            delete_old_track_object(base_name)
            global tracker_mesh
            tracker_mesh = create_pointcloud()
            tracker_mesh.name = base_name

            # Auto-apply Object constraint if it's an object track
            if track_obj_name != "Camera":
                c = tracker_mesh.constraints.new('OBJECT_SOLVER')
                c.clip = clip
                c.object = track_obj_name
                bpy.context.view_layer.objects.active = tracker_mesh
                try:
                    bpy.ops.constraint.objectsolver_set_inverse(constraint=c.name)
                except:
                    pass

            generated_material = apply_active_clip_material(tracker_mesh)
            create_tracks_node_tree(tracker_mesh, generated_material)
            apply_camera_projection(tracker_mesh)

            return {'FINISHED'}
        except Exception as e:
            print(e)
            self.report({'ERROR'}, f"Generating Surface Failed: {e}")
            return {'CANCELLED'}


# opening about page
class AboutOpen(bpy.types.Operator):
    bl_idname = "autotrack.aboutopen"
    bl_label = "About AutoTrack"
    bl_description = "Opens the About Page"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.at_about = True
        return {'FINISHED'}


# closing about page
class AboutClose(bpy.types.Operator):
    bl_idname = "autotrack.aboutclose"
    bl_label = "Go Back..."
    bl_description = "Closes the About Page"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.at_about = False
        return {'FINISHED'}


# defining the PT panel
class UIPanel(bpy.types.Panel):
    bl_label = "AutoTrack Settings"
    bl_idname = "autotrack_PT_panel"
    bl_space_type = 'CLIP_EDITOR'
    bl_region_type = 'UI'
    bl_category = "AutoTrack"

    def draw_header(self, context):
        self.layout.label(text="", icon='TRACKER')

    def draw(self, context):
        clip = context.edit_movieclip
        layout = self.layout
        cam = bpy.context.scene.camera

        if context.scene.at_about:
            box = self.layout.box()
            row = box.row()
            row.alignment = 'CENTER'
            row.alert = True
            row.label(text=f"AutoTrack v5.1.2", icon='TRACKER')
            row = box.row()
            row.alignment = 'CENTER'
            row.label(text="Created by Siemen Lens")
            box.separator()
            col = box.column(align=True)
            col.scale_y = 1.2
            op = col.operator("wm.url_open", text="Discord Support", icon='COMMUNITY')
            op.url = "https://discord.gg/KrP4RhhsdX"
            op = col.operator("wm.url_open", text="Report a Bug", icon='ERROR')
            op.url = "https://github.com/SiemenLens/AutoTrack/issues"
            op = col.operator("wm.url_open", text="Open Extension Page", icon='BLENDER')
            op.url = "https://extensions.blender.org/add-ons/siemen-lens-blender-autotrack/"
            box.separator()
            sub = box.row()
            sub.scale_y = 1.5
            sub.operator("autotrack.aboutclose", text="Go Back", icon='PANEL_CLOSE')
        else:
            if not context.scene.at_is_running:
                layout.operator("autotrack.aboutopen", icon='WORLD')
            if context.scene.at_is_finished and clip and cam:
                resultsbox = layout.box()
                resultsbox.scale_y = 1
                resultsbox.label(text=context.scene.at_result_message, icon="INFO")
                layout.separator()

            if not context.scene.at_is_running:
                if clip:
                    scenebox = layout.box()
                    scenebox.label(text="Scene Settings", icon="VIEW_CAMERA")
                    scenebox.prop(context.scene, "option_setsceneframe")
                    if not context.scene.option_setsceneframe:
                        row = scenebox.row()
                        row.prop(context.scene, "frame_start", text="Begin")
                        row.prop(context.scene, "frame_end", text="End")
                        scenebox.separator()
                    scenebox.prop(context.scene, "option_tripod", icon="CON_CAMERASOLVER")
                    scenebox.prop(context.scene, "option_focallength")
                    scenebox.prop(context.scene, "option_sensor_dropdown")
                    if context.scene.option_sensor_dropdown == "OPT5":
                        if context.edit_movieclip:
                            scenebox.prop(context.space_data.clip.tracking.camera, "sensor_width", text="Sensor Width")

                    if context.scene.at_is_finished and context.scene.resolve_buttonvisible:
                        scenebox.operator("autotrack.quickresolve", icon='TRACKER_DATA')

                    layout.separator()

                    markerbox = layout.box()
                    if context.scene.collapse_markerplacement:
                        icon = 'TRIA_RIGHT'
                    else:
                        icon = 'TRIA_DOWN'
                    markerbox.prop(context.scene, "collapse_markerplacement", text="Marker Placement Settings",
                                   icon=icon, emboss=False)
                    if not context.scene.collapse_markerplacement:
                        try:
                            annotation = getattr(clip, "annotation", None) or getattr(clip, "grease_pencil", None)
                            active_track = clip.tracking.objects.active
                            if annotation and clip and active_track:
                                mapping = context.scene.at_object_mappings.get(active_track.name)
                                if mapping:
                                    markerboxrow = markerbox.row(align=True)
                                    markerboxrow.prop(mapping, "use_annotation", text="Create Zones using Annotations")
                                    if mapping.use_annotation:
                                        markerboxrow.prop(mapping, "annotation_mode", text="")
                                        markerbox.operator("autotrack.cleargreasepencil", icon="BRUSH_DATA")
                                    markerbox.separator()
                        except:
                            pass
                        markerbox.prop(context.scene, "option_markerthreshold")
                        markerbox.prop(context.scene, "option_markerscale")
                        markerbox.prop(context.scene, "option_markerdistance")
                        markerbox.prop(context.scene, "option_markers_retention")
                        markerbox.prop(context.scene, "option_marker_frame_interval")
                        markerbox.prop(context.scene, "option_min_track_length")
                        markerbox.operator("autotrack.testmarkers", icon='TEXTURE')
                        layout.separator()

                    solverbox = layout.box()
                    if context.scene.collapse_solver:
                        icon = 'TRIA_RIGHT'
                    else:
                        icon = 'TRIA_DOWN'
                    solverbox.prop(context.scene, "collapse_solver", text="Solver Settings", icon=icon, emboss=False)
                    if not context.scene.collapse_solver:
                        cleanupbox = solverbox.box()
                        cleanupbox.prop(context.scene, "option_filterpasses")
                        if context.scene.option_filterpasses == 'OPT2' or context.scene.option_filterpasses == 'OPT3':
                            cleanupbox.prop(context.scene, "option_tracks_prefiltering_perc")
                        if context.scene.option_filterpasses == 'OPT3':
                            cleanupbox.prop(context.scene, "option_tracks_cleanup_perc")
                        solverbox.prop(context.scene, "option_solveriterations")
                        refinebox = solverbox.box()
                        refine = refinebox.row()
                        refine.prop(context.scene, "option_refinefocallength")
                        refine.prop(context.scene, "option_refinedistortion")
                        if clip:
                            customlens = solverbox.box()
                            customlens.prop(context.scene, "option_customizeopticalcenter", icon='SNAP_FACE_CENTER')
                            if context.scene.option_customizeopticalcenter:
                                customlens.prop(context.edit_movieclip.tracking.camera, "principal_point", text="")
                            customlens.prop(context.scene, "option_customizeradial", icon='GRID')
                            if context.scene.option_customizeradial:
                                customlens.prop(context.edit_movieclip.tracking.camera, "k1", text="K1")
                                customlens.prop(context.edit_movieclip.tracking.camera, "k2", text="K2")
                                customlens.prop(context.edit_movieclip.tracking.camera, "k3", text="K3")
                        layout.separator()
                    # OBJECT TRACKING UI LIST
                    objtrackbox = layout.box()
                    if context.scene.collapse_objecttracking:
                        icon = 'TRIA_RIGHT'
                    else:
                        icon = 'TRIA_DOWN'
                    objtrackbox.prop(context.scene, "collapse_objecttracking", text="Object Tracking (Beta)",
                                     icon=icon, emboss=False)

                    if not context.scene.collapse_objecttracking:

                        # Check if any object tracks have been added (1 means only default 'Camera' exists)
                        if len(clip.tracking.objects) > 1:

                            # Annotation Settings (Outside & Above the List Box)
                            cam_track = clip.tracking.objects.get("Camera")
                            camera_is_solved = cam_track and cam_track.reconstruction.is_valid
                            active_track = clip.tracking.objects.active

                            # Only warn if an Object is selected AND the Camera isn't solved yet
                            if active_track and active_track.name != "Camera" and not camera_is_solved:
                                warningbox = objtrackbox.box()
                                warningbox.alert = True
                                warningbox.label(text="Camera Not Solved Yet!", icon='ERROR')

                            active_track = clip.tracking.objects.active
                            if active_track:
                                mapping = context.scene.at_object_mappings.get(active_track.name)
                                if mapping:
                                    ann_row = objtrackbox.row(align=True)
                                    ann_row.label(text=f"Annotation Mask ({active_track.name}):",
                                                  icon='GREASEPENCIL')
                                    ann_row.prop(mapping, "use_annotation", text="")
                                    if mapping.use_annotation:
                                        ann_row.prop(mapping, "annotation_mode", text="")
                                    objtrackbox.operator("autotrack.cleargreasepencil", icon="BRUSH_DATA")
                                    objtrackbox.separator()

                            # Track Objects List Box
                            list_box = objtrackbox.box()

                            for tr_obj in clip.tracking.objects:
                                row = list_box.row(align=True)
                                is_active = (tr_obj == clip.tracking.objects.active)

                                # Tracking Object Selection Column
                                name_col = row.column(align=True)
                                op = name_col.operator("autotrack.set_active_track_object",
                                                       text=tr_obj.name,
                                                       icon='VIEW_CAMERA' if tr_obj.name == "Camera" else 'OBJECT_DATA',
                                                       depress=is_active)
                                op.obj_name = tr_obj.name

                                if tr_obj.name != "Camera":
                                    # Remove Tracking Object Column ('X')
                                    rm_col = row.column(align=True)
                                    rm_op = rm_col.operator("autotrack.remove_track_object", text="", icon='X')
                                    rm_op.obj_name = tr_obj.name

                            list_box.operator("clip.tracking_object_new", text="Add Object Track", icon='ADD')

                            # ACTIVE TRACK PARAMETERS (Moved Below the Object Tracker List)
                            active_track = clip.tracking.objects.active
                            if active_track and active_track.name != "Camera":
                                objtrackbox.separator()

                                mapping = context.scene.at_object_mappings.get(active_track.name)
                                if mapping:
                                    act_row = objtrackbox.row()
                                    act_row.prop(mapping, "obj", text="Linked Object", icon='OUTLINER_OB_MESH')

                                    act_scale_row = objtrackbox.row()
                                    # We now use the wrapper property we made above to get custom sensitivity
                                    act_scale_row.prop(mapping, "distance_scale", text="Distance (Scale)")

                        else:
                            # If no objects are in the list, ONLY show the Add Object button
                            objtrackbox.operator("clip.tracking_object_new", text="Add Object Track", icon='ADD')

                        layout.separator()

                    if aud_present:
                        miscbox = layout.box()
                        if context.scene.collapse_misc:
                            icon = 'TRIA_RIGHT'
                        else:
                            icon = 'TRIA_DOWN'
                        miscbox.prop(context.scene, "collapse_misc", text="Miscellaneous Settings", icon=icon,
                                     emboss=False)
                        if not context.scene.collapse_misc:
                            miscbox.prop(context.scene, "option_soundfinish", icon='FILE_SOUND')

                    layout.separator()

                    if context.scene.at_is_finished and clip and cam:
                        generatesurfacebox = layout.box()
                        generatesurfacebox.label(text="Surface Generator Settings", icon='OUTLINER_DATA_SURFACE')
                        generatesurfacebox.operator("autotrack.generatesurface")

                        track_obj_name = clip.tracking.objects.active.name if clip.tracking.objects.active else "Camera"
                        base_name = "Environment_PointCloudSurface" if track_obj_name == "Camera" else f"{track_obj_name}_PointCloudSurface"

                        surface_obj = None
                        for obj in bpy.context.scene.objects:
                            if obj.name == base_name or obj.name.startswith(base_name + "."):
                                surface_obj = obj
                                break

                        if surface_obj:
                            try:
                                mod = surface_obj.modifiers.get("Surface Generator")
                                if mod and mod.node_group:
                                    for item in mod.node_group.interface.items_tree:
                                        if item.name in ["Resolution", "Connection Radius"]:
                                            try:
                                                if hasattr(mod, "properties") and hasattr(mod.properties, "inputs"):
                                                    inputs_collection = mod.properties.inputs
                                                    try:
                                                        socket_obj = getattr(inputs_collection, item.identifier)
                                                    except AttributeError:
                                                        socket_obj = inputs_collection[item.identifier]
                                                    generatesurfacebox.prop(socket_obj, "value", text=item.name)
                                                else:
                                                    prop_exists = False
                                                    try:
                                                        _ = mod[item.identifier]
                                                        prop_exists = True
                                                    except Exception:
                                                        pass
                                                    if prop_exists:
                                                        generatesurfacebox.prop(mod, f'["{item.identifier}"]',
                                                                                text=item.name)
                                                    else:
                                                        generatesurfacebox.prop(item, "default_value", text=item.name)

                                                        surface_obj_name = surface_obj.name

                                                        def init_mod_prop(ident=item.identifier, val=item.default_value,
                                                                          obj_n=surface_obj_name):
                                                            try:
                                                                obj = bpy.data.objects.get(obj_n)
                                                                if obj:
                                                                    m = obj.modifiers.get("Surface Generator")
                                                                    if m: m[ident] = val
                                                            except Exception:
                                                                pass
                                                            return None

                                                        bpy.app.timers.register(init_mod_prop, first_interval=0.1)
                                            except Exception as e:
                                                print(f"Could not draw UI for {item.name}: {e}")
                            except Exception as e:
                                print(f"UI Error: {e}")

                else:
                    box = layout.box()
                    row = box.row()
                    row.alignment = 'CENTER'
                    row.alert = True
                    row.label(text="Welcome to AutoTrack!", icon='TRACKER')
                    row2 = box.row()
                    row2.alignment = 'CENTER'
                    row2.label(text="Import a video to get started.")

                    row_btns = box.row(align=True)
                    row_btns.operator("clip.open", icon='FILE_MOVIE')

                if clip:
                    track_obj_name = "Camera"
                    if clip.tracking.objects.active:
                        track_obj_name = clip.tracking.objects.active.name

                    layout.separator()
                    starttrackingrow = layout.row()
                    starttrackingrow.scale_y = 2
                    starttrackingrow.alert = True
                    starttrackingrow.operator("autotrack.runtracking", text=f"Start {track_obj_name} Tracking!",
                                              icon='CON_FOLLOWTRACK')
                    layout.separator()

            if context.scene.at_is_running:
                layout.separator()
                statusmessagebox = layout.box()
                statusmessagebox.label(text=context.scene.at_status_message, icon='INFO')
                if context.scene.at_is_solving:
                    bestsolvebox = layout.box()
                    bestsolvebox.label(text=context.scene.at_bestsolve, icon='CON_CAMERASOLVER')
                    if not context.scene.at_warning == "":
                        warningbox = layout.box()
                        warningbox.alert = True
                        warningbox.label(text=context.scene.at_warning, icon='ERROR')
                layout.separator()
                box = layout.box()
                box.alert = True
                box.scale_y = 1.5
                box.label(text=context.scene.at_status, icon="CON_FOLLOWTRACK")
                box.prop(context.scene, "at_progress", text="Progress", slider=True)
                layout.separator()
                layout.label(text=context.scene.at_remainingtime, icon="SORTTIME")
                warningrow = layout.row()
                warningrow.alert = True
                warningrow.label(text="Blender may freeze. Do not touch", icon="FREEZE")


# Persistent timer logic to sync Annotations across multiple tracking objects
@bpy.app.handlers.persistent
def sync_annotations():
    # 1. Background task to automatically register CollectionProperty object mappings without UI drawing context conflicts
    for scene in bpy.data.scenes:
        for clip in bpy.data.movieclips:
            for tr_obj in clip.tracking.objects:
                if tr_obj.name not in scene.at_object_mappings:
                    item = scene.at_object_mappings.add()
                    item.name = tr_obj.name

    # 2. Handles the annotation swapping for the specific tracking object selected in the active clip editor
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'CLIP_EDITOR':
                space = area.spaces.active
                if space and space.clip:
                    clip = space.clip
                    track_obj = clip.tracking.objects.active
                    if not track_obj: continue

                    track_obj_name = track_obj.name
                    expected_name = f"Ann_{clip.name}_{track_obj_name}"

                    attr_name = "annotation" if hasattr(clip, "annotation") else "grease_pencil"
                    current_gp = getattr(clip, attr_name, None)
                    data_storage = bpy.data.annotations if hasattr(bpy.data, "annotations") else bpy.data.grease_pencils

                    if current_gp:
                        if not current_gp.name.startswith("Ann_"):
                            # Try binding the existing / initially drawn one to the current track object
                            try:
                                current_gp.name = expected_name
                            except:
                                pass
                        elif current_gp.name != expected_name:
                            # User switched tracking object. Swap it!
                            target_gp = data_storage.get(expected_name)
                            if target_gp:
                                setattr(clip, attr_name, target_gp)
                            else:
                                try:
                                    new_gp = data_storage.new(expected_name)
                                    setattr(clip, attr_name, new_gp)
                                except:
                                    setattr(clip, attr_name, None)
                    else:
                        # Re-attach it automatically if we know one exists
                        target_gp = data_storage.get(expected_name)
                        if target_gp:
                            setattr(clip, attr_name, target_gp)
    return 0.5


classes = (
    AutoTrackObjectMapping,
    SetActiveTrackObject,
    RemoveTrackObject,
    Runtracking,
    QuickResolve,
    UIPanel,
    TestMarkers,
    ClearGreasePencil,
    GenerateSurface,
    AboutOpen,
    AboutClose
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.at_object_mappings = bpy.props.CollectionProperty(type=AutoTrackObjectMapping)

    if not bpy.app.timers.is_registered(sync_annotations):
        bpy.app.timers.register(sync_annotations, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(sync_annotations):
        bpy.app.timers.unregister(sync_annotations)

    del bpy.types.Scene.at_object_mappings

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()