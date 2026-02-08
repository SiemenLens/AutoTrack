# Siemen Lens

bl_info = {
    "name": "AutoTrack",
    "author": "Siemen Lens",
    "version": (4, 0, 2),  # on publish : don't forget to update version in about menu too
    "blender": (4, 0, 0),
    "location": "Movie Clip Editor > Sidebar > AutoTrack Tab",
    "description": "Automatically track imported footage with optimized solving logic.",
    "category": "VFX",
}

# imports necessary to make the script work
# we use random to generate random keyframes for solving
# we use time to estimate how long the tracking process is going to take.
import bpy
import math
import random
import time


# class for the main automatic tracking process
class Runtracking(bpy.types.Operator):
    bl_idname = "autotrack.runtracking"
    bl_label = "Start Tracking!"
    bl_description = "Run the tracking process"
    bl_options = {'REGISTER'}

    def update_camera_parameters(self, context):
        """
        Handles the changes made in the camera (scene) parameters panel, like automatically updating the required parameters and making the quick resolve button appear.
        """

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
            # if the preset is custom, the parameter is directly used in the UI, no updating is required
            pass

        # set the focal length option to the one the user defined in the PT panel, same with the tripod option
        clip.tracking.camera.focal_length = self.option_focallength
        clip.tracking.settings.use_tripod_solver = context.scene.option_tripod

        # make the quick resolve button appear if a clip has been imported and if there's a resolved camera
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

    zone_types = [
        ('OPT1', "Exclude", "Exclude the annotated area from tracking", 'FULLSCREEN_ENTER', 1),
        ('OPT2', "Only", "Only keep annotated area in tracking", 'FULLSCREEN_EXIT', 2)
    ]

    filter_passes = [
        (
        'OPT1', "Fast Pass (Legacy)", "Use a simple and fast filtering algorithm, not very versatile and may not work.",
        'PIVOT_MEDIAN', 1),
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
        min=0.01,
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

    bpy.types.Scene.option_annotation = bpy.props.BoolProperty(
        name="Create Zones using Annotations",
        description="Create zones using the annotation feature, can either exclude or include trackers",
        default=True,
    )
    bpy.types.Scene.option_annotation_mode = bpy.props.EnumProperty(
        name="",
        description="What mode should annotation work in?",
        items=zone_types,
        default='OPT1',
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
        name="I was using a tripod",
        description="Were you using a tripod to shoot this video?",
        default=False,
        update=update_camera_parameters
    )

    bpy.types.Scene.finishing_up = bpy.props.BoolProperty(
        default=False,
    )

    bpy.types.Scene.at_is_finished = bpy.props.BoolProperty(
        default=False
    )

    bpy.types.Scene.at_is_running = bpy.props.BoolProperty(
        default=False
    )
    bpy.types.Scene.at_is_solving = bpy.props.BoolProperty(
        default=False
    )

    bpy.types.Scene.resolve_buttonvisible = bpy.props.BoolProperty(
        default=False
    )
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

    bpy.types.Scene.collapse_markerplacement = bpy.props.BoolProperty(
        default=True
    )
    bpy.types.Scene.collapse_solver = bpy.props.BoolProperty(
        default=True
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

    bpy.types.Scene.at_about = bpy.props.BoolProperty(
        default=False
    )

    def execute(self, context):
        # function definitions

        def set_frame(frame):
            """
            easy function for the rest of the script to quickly skip to other frames in the timeline while tracking, we're not using the default Blender operator for this as it doesn't work well during a running process.
            """
            frame = int(math.ceil(frame))
            context.scene.frame_current = frame
            for space in area.spaces:
                if space.type == 'CLIP_EDITOR':
                    space.clip_user.frame_current = frame

        def refresh_screen():
            """
            easy function for the rest of the script to refresh the screen when necessary. Blender does not do this by default when a tracking process is happening. It also handles the calculation for updating the time remaining
            """
            if scene.at_progress > 0:
                # calculation of time remaining
                time_elapsed = time.time() - begin_time
                remaining_time = (time_elapsed / scene.at_progress) * (100 - scene.at_progress)
            else:
                # safety fallback to prevent division by zero
                remaining_time = 0
            # formatting the remaining time into a nice message
            mins, secs = divmod(int(remaining_time), 60)
            scene.at_remainingtime = f"Time Remaining: {mins:02d}:{secs:02d}"

            # update the screen
            try:
                with context.temp_override(window=context.window, area=area):
                    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                bpy.context.view_layer.update()
            except Exception as e:
                print(f"Could not refresh screen: {e}")

        def track_markers_sequence(backwards, start_frame, end_frame, progressincrease):
            """
            tracks the markers defined from start_frame to end_frame in the specified direction.
            """
            set_frame(start_frame)
            # check how many frames it has to track
            computable_frames = math.fabs(start_frame - end_frame)
            print(f"Running tracking for {computable_frames} frames")
            count = start_frame

            for frame in range(int(math.fabs(start_frame - end_frame))):
                # run a loop for each frame it has to track, where we set the frame, update the progress variable and track the frame.
                set_frame(count)
                if backwards:
                    count -= 1
                else:
                    count += 1

                if scene.frame_start <= count <= scene.frame_end:
                    refresh_screen()
                    time.sleep(0.05)  # Delay to lower crashing chances due to RAM race conditions.
                    try:
                        bpy.ops.clip.track_markers(backwards=backwards, sequence=False)  # track one frame
                    except Exception as e:
                        print(f"Tracking for frame {count} failed: {e}")
                    time.sleep(0.05)  # Delay to lower crashing chances due to RAM race conditions.
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

        def scan_markers(try_out=False):
            """
            Small script to scan for markers with the user defined parameters in the PT panel, new version of this script also includes the handling of the annotations
            """
            refresh_screen()
            # calculate what the pattern and search size should be based on the video resolution
            if clip.size[0] > clip.size[1]:
                largest_side = clip.size[0]
            else:
                largest_side = clip.size[1]
            scale_factor = largest_side / 1920

            clip.tracking.settings.default_pattern_size = int((50 * scale_factor) * (scene.option_markerscale / 100))
            clip.tracking.settings.default_search_size = int((250 * scale_factor) * (scene.option_markerscale / 100))

            # setup default variable
            placement = 'FRAME'
            # we will need to handle processing in the grease pencil/ annotation frames because when scanning for markers, by default for some reason, Blender just assumes we want to scan on all annotations while we just want to scan on the current frame's annotation.
            try:
                temp_gp = None
                # check for either annotation or grease pencil, since the naming changed between blender 4.0 and 5.0
                attr_name = "annotation" if hasattr(clip, "annotation") else "grease_pencil"
                # save the original drawing so we can put it back later
                original_gp = getattr(clip, attr_name, None)
                # only run this if the user wants to use drawings
                if scene.option_annotation:

                    # try to find drawings on the clip first
                    source_gp = original_gp

                    # if nothing on clip, check the scene
                    if not source_gp:
                        source_gp = getattr(context.scene, attr_name, None)

                    # if we found drawings somewhere, let's process them
                    if source_gp:

                        # set the detection mode based on user choice
                        if scene.option_annotation_mode == "OPT1":
                            placement = 'OUTSIDE_GPENCIL'
                        else:
                            placement = 'INSIDE_GPENCIL'

                        # make a copy so we don't break the real drawing
                        temp_gp = source_gp.copy()
                        current_frame = scene.frame_current

                        # clean up the copy to only show the current frame
                        for layer in temp_gp.layers:
                            valid_frame = None

                            # find the frame that is visible right now
                            for frame in layer.frames:
                                if frame.frame_number <= current_frame:
                                    # keep updating until we find the closest one
                                    if valid_frame is None or frame.frame_number > valid_frame.frame_number:
                                        valid_frame = frame

                            # delete all other frames from this layer
                            for frame in list(layer.frames):
                                if frame != valid_frame:
                                    layer.frames.remove(frame)
                        # put our filtered copy onto the clip
                        setattr(clip, attr_name, temp_gp)

            except:
                placement = 'FRAME'  # if anything fails just don't use the drawings

            bpy.ops.clip.detect_features(margin=int((30 * scale_factor) * (scene.option_markerscale / 100)),
                                         placement=placement,
                                         threshold=scene.option_markerthreshold,
                                         min_distance=int((1.5 if try_out else 1) * (
                                                     (scale_factor) * context.scene.option_markerdistance)))

            try:
                # put the original drawing back
                setattr(clip, attr_name, original_gp)
                # delete the temporary copy from memory
                if temp_gp:
                    if hasattr(bpy.data, "annotations"):
                        bpy.data.annotations.remove(temp_gp)
                    else:
                        bpy.data.grease_pencils.remove(temp_gp)
            except:
                pass

        def get_solve_error():
            """
            Helper function to simply obtain the solve error generated Blender after solving in main script
            """

            track_obj = clip.tracking.objects.get('Camera')
            # check if there's a camera object and if the object is actually a camera
            if track_obj and track_obj.is_camera:
                solve_error = track_obj.reconstruction.average_error
                return solve_error

        def get_reconstructed_count():
            """
            Count % of tracks that have a 3D bundle (successful reconstruction).
            This is important for the solving algorithm we made.
            """

            total_tracks = len(clip.tracking.tracks)
            reconstructed_count = 0
            # iterate through the found markers to see which one has a bundle.
            for track in clip.tracking.tracks:
                if track.has_bundle:
                    reconstructed_count += 1
            return reconstructed_count / total_tracks

        def refine_solve(focal, radial):
            global refinement_solves

            prevprincipalpoint0 = prevprincipalpoint1 = 0
            prevradialk1 = prevradialk2 = prevradialk3 = 0

            # reset everything if no custom lens settings are used
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

                # set custom lens settings back
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
            """
            Returns the number of frames where fewer than 'threshold' solved tracks exist.
            """
            if not clip:
                return 0

            failed_frames = 0
            start_frame = context.scene.frame_start
            end_frame = context.scene.frame_end
            for f in range(start_frame, end_frame + 1):
                valid_bundles_on_frame = 0
                for track in clip.tracking.tracks:
                    if track.has_bundle:
                        if track.markers.find_frame(f):
                            valid_bundles_on_frame += 1
                if valid_bundles_on_frame < threshold:
                    failed_frames += 1
            return failed_frames

        def obtain_percentile_of_trackers(value):
            data = tuple(t.average_error for t in clip.tracking.tracks)
            sorted_data = sorted(data)
            n = len(sorted_data)
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
                    # how much solves should we keep when we sort them from best to worst?
                    top_current_amount = int(len(current_keyframe_solves) / 2)

                    # sort the solves from best to worst sorted on track reconstruction
                    top_current_reprojection = sorted(current_keyframe_solves, key=lambda x: x[3], reverse=True)[
                                               :top_current_amount]

                    # choose the entry with the best solve error from the top_reprojection collection
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
                    # how much solves should we keep when we sort them from best to worst?
                    best_current_solve = min(range(len(current_refine_solves)),
                                             key=lambda i: current_refine_solves[i][0])
                    context.scene.at_bestsolve = f"Current Best Solve: {round(current_refine_solves[best_current_solve][0], 2)}px"
            except Exception as e:
                print(e)

        def solve_camera(iterations, initialsolve=False, cleanupsolve=False):
            """
            Main script for the camera solving with iterations
            """
            # make sure the keyframe selection option is turned off, our script will define it.
            scene.finishing_up = False
            clip.tracking.settings.use_keyframe_selection = False
            clip.tracking.settings.refine_intrinsics_focal_length = False
            clip.tracking.settings.refine_intrinsics_principal_point = False
            clip.tracking.settings.refine_intrinsics_radial_distortion = False
            context.scene.at_is_solving = True

            if not bpy.context.scene.camera:
                cam_data = bpy.data.cameras.new(name="Camera")
                cam = bpy.data.objects.new(name="Camera", object_data=cam_data)
                bpy.context.scene.collection.objects.link(cam)
                bpy.context.scene.camera = cam

            cam = bpy.context.scene.camera
            try:
                for constraint in [c for c in cam.constraints if c.type == 'CAMERA_SOLVER']:
                    cam.constraints.remove(constraint)
                cam.constraints.new(type='CAMERA_SOLVER')
            except Exception as e:
                print(e)
            cam.rotation_euler[0] = 1.5708
            cam.rotation_euler[1] = 0
            cam.rotation_euler[2] = 1.5708
            cam.location[0] = 10
            cam.location[1] = 0
            cam.location[2] = 0

            track_obj = clip.tracking.objects.get('Camera')
            keyframe_solves = []  # collection for the different solves we're going to make
            attempts = iterations
            if initialsolve:
                context.scene.at_status_message = f"Performing camera solves... (1/{attempts})"  # initial value for status message
            else:
                context.scene.at_status_message = f"Performing final solves... (1/{attempts})"  # initial value for status message

            context.scene.at_bestsolve = f"No solve has been made yet"
            refresh_screen()
            # iterate in solves until we got the required amount of iterations, introducing an error count for when the solve at specific keyframe fails.
            errorcount = 0
            scene.at_warning = ""
            while len(
                    keyframe_solves) < attempts and errorcount < 1000:  # allowing a max of 1000 retries to prevent being stuck in a loop of impossible solves
                # using a random value for both keyframes
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

                    print(
                        f"I got a solve error of {solve_error} ({track_reconstruction * 100}%) for keyframes {keyframe_a},{keyframe_b}")
                    # append the results of the successful solve to our collection
                    keyframe_solves.append([keyframe_a, keyframe_b, solve_error, track_reconstruction, failed_frames])
                    best_current_solve(keyframe_solves)
                    refresh_screen()
                    # update the progress bar and status message
                    if cleanupsolve:
                        if scene.option_refinefocallength or scene.option_refinedistortion:
                            scene.at_progress += 10 / attempts
                        else:
                            scene.at_progress += 15 / attempts
                    else:
                        if scene.option_refinefocallength or scene.option_refinedistortion:
                            scene.at_progress += 20 / attempts
                        else:
                            scene.at_progress += 30 / attempts

                    if initialsolve:
                        context.scene.at_status_message = f"Performing camera solves... ({len(keyframe_solves) + 1}/{attempts})"
                    else:
                        context.scene.at_status_message = f"Performing final solves... ({len(keyframe_solves) + 1}/{attempts})"
                except Exception as e:
                    print(f"This solve failed. Retrying, this is retry nr. {errorcount}/1000. {e}")
                    errorcount += 1

            # make sure at least one solve is successful
            if len(keyframe_solves) > 0:
                # how much solves should we keep when we sort them from best to worst?
                top_amount = int(len(keyframe_solves) / 2)

                # sort the solves from best to worst sorted on track reconstruction
                top_reprojection = sorted(keyframe_solves, key=lambda x: x[3], reverse=True)[:top_amount]

                # choose the entry with the best solve error from the top_reprojection collection
                best_solve = min(range(len(top_reprojection)), key=lambda i: top_reprojection[i][2])
                print(
                    f"the best solve was keyframe {top_reprojection[best_solve][0]}, {top_reprojection[best_solve][1]}. Error count {top_reprojection[best_solve][2]}px with a reconstructed count of {top_reprojection[best_solve][3]}.")

                # set the keyframes that led to this good solve
                track_obj.keyframe_a = top_reprojection[best_solve][0]
                track_obj.keyframe_b = top_reprojection[best_solve][1]

                if ((not initialsolve) or (top_reprojection[best_solve][2]) < 1 * scale_factor) and (
                        scene.option_refinefocallength or scene.option_refinedistortion):
                    global refinement_solves
                    scene.finishing_up = True
                    scene.at_progress = 90
                    refinement_solves = []
                    # initial result
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
                        clip.tracking.settings.refine_intrinsics_radial_distortion = refinement_solves[best_solve_refine][3]

                        print("------------------ TOP REFINEMENTS --------------------------")
                        print(refinement_solves)
                        print(
                            f"RESULTS : best solve = index{best_solve_refine} at solve error {refinement_solves[best_solve_refine][0]} {refinement_solves[best_solve_refine][2]} {refinement_solves[best_solve_refine][3]}")
                    else:
                        print("There are no refinements")

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

                # update the result message
                context.scene.at_result_message = f"Finished: {round(get_solve_error(), 2)}px and {round(get_reconstructed_count(), 2) * 100}% reconstructed markers."


            else:
                # if absolutely no solves were successful, cancel the solving
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
            """
            Removes all timeline markers that start with 'AutoTrack'
            """
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

                for track in clip.tracking.tracks:
                    if not include_selected and track.select:
                        continue

                    for marker in track.markers:
                        # Only count if the marker is active and within the frame range
                        if not marker.mute and marker.frame in frame_counts:
                            frame_counts[marker.frame] += 1

                # Check if any frame failed the requirement
                for frame, count in frame_counts.items():
                    if count < min_count:
                        print(f"Frame {frame} failed: Has {count} markers (Needed {min_count})")
                        return False

                return True

            except Exception as e:
                print(f"Error in enough_markers_left: {e}")
                return False

        def deselect_disabled_markers():
            for track in clip.tracking.tracks:
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

        context.scene.at_status_message = "Setting up parameters..."  # initial status message

        # variables to make referencing to specific parts easier
        clip = context.edit_movieclip
        bpy.context.space_data.mode = 'TRACKING'
        scene = bpy.context.scene
        area = context.area

        scene.at_progress = 0  # set the progress counter to 0

        # check if a clip is loaded
        if not clip:
            self.report({'WARNING'}, "No video clip is selected")
            return {'CANCELLED'}

        # check if set scene frame option is toggled, if it isn't, check if our clip covers the timeline.
        # If it doesn't cover the timeline, set the scene frames anyway. Otherwise it's going to fail
        if scene.option_setsceneframe:
            bpy.ops.clip.set_scene_frames()
        else:
            if scene.frame_end > clip.frame_duration:
                scene.frame_end = clip.frame_duration
                self.report({'WARNING'}, "Corrected scene end frame because your video is shorter than your timeline.")
            if scene.frame_start < 1:
                scene.frame_start = 1
                self.report({'WARNING'}, "Corrected scene begin frame because it was below 1.")

        # set the begin and end frames of our scene
        start_frame = scene.frame_start
        end_frame = scene.frame_end

        # Check if frame step is set to 1, this is important because otherwise Blender tracking won't work properly
        if scene.frame_step != 1:
            self.report({'ERROR'}, f"Tracking failed! Scene Frame Step must be 1 to be able to track.")
            return {'CANCELLED'}

        try:
            global begin_time
            begin_time = time.time()  # set the initial start time for the time estimation
            total_frames = end_frame - start_frame  # calculate the total frames of the clip
            clip.tracking.settings.use_tripod_solver = scene.option_tripod  # set tripod solver if the option was enabled

            # reset everything to default:

            if not context.scene.option_customizeopticalcenter:
                clip.tracking.camera.principal_point[0] = 0
                clip.tracking.camera.principal_point[1] = 0

            if not context.scene.option_customizeradial:
                clip.tracking.camera.k1 = 0
                clip.tracking.camera.k2 = 0
                clip.tracking.camera.k3 = 0

            clip.tracking.camera.focal_length = scene.option_focallength

            # set state variables
            context.scene.at_is_running = True
            context.scene.at_is_finished = False
            context.scene.at_is_solving = False
            clip.tracking.settings.default_motion_model = 'Loc'
            clip.tracking.settings.default_pattern_match = 'KEYFRAME'
            # optimise some settings that improve tracking performance
            clip.tracking.settings.use_default_normalization = True
            bpy.context.space_data.show_disabled = True

            # go to the first frame and delete all trackers (markers)
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
                        print(f"Alive markers: {alive_markers}")
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
                min_tracks_prefiltering = int(
                    (least_amount_of_markers * (scene.option_tracks_prefiltering_perc/100)) if least_amount_of_markers > 25 else 20)
                min_tracks_cleanup = int(
                    (least_amount_of_markers * (scene.option_tracks_cleanup_perc/100)) if least_amount_of_markers > 25 else 15)
            else:
                # use default values if the user messed something up, this is to prevent an endless loop from happening
                min_tracks_prefiltering = int((least_amount_of_markers * (0.8)) if least_amount_of_markers > 25 else 20)
                min_tracks_cleanup = int((least_amount_of_markers * (0.6)) if least_amount_of_markers > 25 else 15)

            scene.at_progress = 50

            bpy.ops.clip.select_all(action='DESELECT')

            if not context.scene.option_filterpasses == "OPT1":
                # Global prefilter
                minimum_tracks = min_tracks_prefiltering
                global track_threshold
                track_threshold = 50
                bpy.context.space_data.show_disabled = True
                scene.at_status_message = f"Running global filter... "
                refresh_screen()

                change_filter_threshold(0,False,True)
                while enough_markers_left(minimum_tracks, False) and track_threshold > 15:
                    change_filter_threshold(3, False, True)
                    print(f"Enough markers left! Lowering global filter to {track_threshold}")

                if not enough_markers_left(minimum_tracks, False):
                    while not enough_markers_left(minimum_tracks, False):
                        change_filter_threshold(1, True, True)
                        print(f"Not enough markers detected, upping global filter to {track_threshold}")
                else:
                    print("Enough tracks left over, no need to up the filter again.")


                if not enough_markers_left(minimum_tracks, False):
                    print(
                        f"SOMETHING WENT WRONG WITH DELETION. global filter at threshold {track_threshold}. Won't delete tracks.")
                else:
                    print(f"Reached solution for global filter. Filtering at {track_threshold}")
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
                                print(f"Enough markers left! Lowering filter to {track_threshold}")

                        if not enough_markers_left(minimum_tracks, False):
                            while not enough_markers_left(minimum_tracks, False):
                                change_filter_threshold(1, True, False)
                                print(f"Not enough markers detected, upping filter to {track_threshold}")
                        else:
                            print("Enough tracks left over, no need to up the filter again.")

                        if not enough_markers_left(minimum_tracks, False):
                            print(
                                f"SOMETHING WENT WRONG WITH DELETION. frame {frame[0]} at threshold {track_threshold}. Won't delete tracks.")
                        else:
                            print(f"Reached solution for substep {frame[0]}. Filtering at {track_threshold}")
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

            # set the lens focal length to the focal length defined in the PT menu
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

            # tripod solving should not use the advanced solving algorithm since it doesn't make a difference when not reconstructing a 3D scene
            if (not scene.option_tripod) and (scene.option_filterpasses == 'OPT3'):
                solve_camera(scene.option_solveriterations, True,
                             True)  # advanced solving algorithm we previously defined
                if not scene.finishing_up:
                    percentile_detect = 100
                    minimum_tracks = min_tracks_cleanup
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

            cam = bpy.context.scene.camera
            # if for some reason Blender does not create a camera, it will skip the camera steps
            try:
                cam.data.lens = clip.tracking.camera.focal_length
                context.scene.render.resolution_x = clip.size[0]
                context.scene.render.resolution_y = clip.size[1]
                bpy.ops.clip.set_viewport_background()
            except Exception as e:
                print(e)

            scene.option_focallength = clip.tracking.camera.focal_length

            # hide the quick resolve button if it was visible
            scene.resolve_buttonvisible = False

            # display the result message as an info message
            self.report({'INFO'}, context.scene.at_result_message)

        except Exception as e:
            self.report({'ERROR'}, f"Solving failed! {e}")
            scene.at_result_message = f"Solving failed to complete."
            scene.at_is_running = False
            scene.at_is_finished = True
            return {'CANCELLED'}

        # update state variables
        scene.at_is_running = False
        scene.at_is_finished = True


        return {'FINISHED'}


# class for the quick resolve button / operator
class QuickResolve(bpy.types.Operator):
    bl_idname = "autotrack.quickresolve"
    bl_label = "Quick Resolve"
    bl_description = "Run the solver without re-tracking"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        # variable to make referencing to specific parts easier
        clip = context.edit_movieclip

        clip.tracking.settings.use_tripod_solver = context.scene.option_tripod

        # hide the resolve button since we're resolving right now.
        context.scene.resolve_buttonvisible = False

        # check if a clip has been added, if none is added, cancel the process.
        if not clip:
            self.report({'ERROR'}, "No clip selected")
            return {'CANCELLED'}
        try:
            bpy.ops.clip.solve_camera()  # solve the camera via blender's solve operator, since we already know the optimal keyframe values
            context.scene.option_focallength = clip.tracking.camera.focal_length
        except Exception as e:
            self.report({'ERROR'}, f"Quick Resolve failed: {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Quick Resolve completed! Please re-run for a more accurate result.")
        return {'FINISHED'}


# class for the test markers button / operator, which allows the user to quickly check how the markers will be placed
class TestMarkers(bpy.types.Operator):
    bl_idname = "autotrack.testmarkers"
    bl_label = "Test Markers"
    bl_description = "Test the placement of markers on the current frame"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # variable to make referencing to specific parts easier
        clip = context.edit_movieclip

        if clip:
            try:
                # delete the current markers
                scene = context.scene
                bpy.context.space_data.show_disabled = True
                bpy.ops.clip.select_all(action='SELECT')
                bpy.ops.clip.delete_track()
                bpy.context.space_data.show_disabled = False

                # calculate what the pattern and search size should be based on the video resolution
                if clip.size[0] > clip.size[1]:
                    largest_side = clip.size[0]
                else:
                    largest_side = clip.size[1]
                scale_factor = largest_side / 1920

                clip.tracking.settings.default_pattern_size = int(
                    (50 * scale_factor) * (scene.option_markerscale / 100))
                clip.tracking.settings.default_search_size = int(
                    (250 * scale_factor) * (scene.option_markerscale / 100))

                # setup default variable
                placement = 'FRAME'
                # we will need to handle processing in the grease pencil/ annotation frames because when scanning for markers, by default for some reason, Blender just assumes we want to scan on all annotations while we just want to scan on the current frame's annotation.
                try:
                    temp_gp = None
                    # check for either annotation or grease pencil, since the naming changed between blender 4.0 and 5.0
                    attr_name = "annotation" if hasattr(clip, "annotation") else "grease_pencil"
                    # save the original drawing so we can put it back later
                    original_gp = getattr(clip, attr_name, None)
                    # only run this if the user wants to use drawings
                    if scene.option_annotation:

                        # try to find drawings on the clip first
                        source_gp = original_gp

                        # if nothing on clip, check the scene
                        if not source_gp:
                            source_gp = getattr(context.scene, attr_name, None)

                        # if we found drawings somewhere, let's process them
                        if source_gp:

                            # set the detection mode based on user choice
                            if scene.option_annotation_mode == "OPT1":
                                placement = 'OUTSIDE_GPENCIL'
                            else:
                                placement = 'INSIDE_GPENCIL'

                            # make a copy so we don't break the real drawing
                            temp_gp = source_gp.copy()
                            current_frame = scene.frame_current

                            # clean up the copy to only show the current frame
                            for layer in temp_gp.layers:
                                valid_frame = None

                                # find the frame that is visible right now
                                for frame in layer.frames:
                                    if frame.frame_number <= current_frame:
                                        # keep updating until we find the closest one
                                        if valid_frame is None or frame.frame_number > valid_frame.frame_number:
                                            valid_frame = frame

                                # delete all other frames from this layer
                                for frame in list(layer.frames):
                                    if frame != valid_frame:
                                        layer.frames.remove(frame)

                            # put our filtered copy onto the clip
                            setattr(clip, attr_name, temp_gp)
                except:
                    placement = 'FRAME'  # if anything fails just don't use the drawings

                bpy.ops.clip.detect_features(margin=int((30 * scale_factor) * (scene.option_markerscale / 100)),
                                             placement=placement,
                                             threshold=context.scene.option_markerthreshold,
                                             min_distance=int(((scale_factor) * context.scene.option_markerdistance)))

                try:
                    # put the original drawing back
                    setattr(clip, attr_name, original_gp)
                    # delete the temporary copy from memory
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
            attr_name = "annotation"  # The name of the property on the object
            data_storage = bpy.data.annotations  # Where the data is stored
        else:
            attr_name = "grease_pencil"
            data_storage = bpy.data.grease_pencils

            # create a list of all objects we want to check (Clips + Scene)
        objects_to_check = list(bpy.data.movieclips)
        objects_to_check.append(context.scene)

        # find data to remove and clear the object references
        items_to_delete = set()
        for obj in objects_to_check:
            data = getattr(obj, attr_name, None)

            if data:
                items_to_delete.add(data)
                # clear the link on the object (set obj.annotation = None)
                setattr(obj, attr_name, None)

        # remove the actual data blocks from memory
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
                """
                Adds a UV Project modifier to the mesh_obj, using the active scene camera
                and correcting for aspect ratio.
                """
                scene = bpy.context.scene
                camera = scene.camera

                if not camera:
                    print("Error: No active camera found in the scene to project from.")
                    return

                # 1. Ensure the mesh has a UV Map layer
                # The modifier needs a target UV map to write the projected coordinates to.
                if not mesh_obj.data.uv_layers:
                    mesh_obj.data.uv_layers.new(name="Projected_UV")

                # 2. Add the 'UV Project' Modifier
                mod = mesh_obj.modifiers.new(name="Camera_Projection", type='UV_PROJECT')

                # 3. Assign the Camera
                # The modifier allows multiple projectors, we set the first one.
                mod.projectors[0].object = camera

                # 4. Set the UV Map target
                # Defaults to the active one, but explicitly setting it is safer.
                mod.uv_layer = mesh_obj.data.uv_layers[0].name

                # 5. Fix Aspect Ratio
                # By default, UV Project assumes a 1:1 ratio. We must match the render resolution.
                res_x = scene.render.resolution_x
                res_y = scene.render.resolution_y

                # Calculate aspect ratio
                if res_y > 0:
                    # If the image is 1920x1080 (1.77 ratio), we adjust the scale to match.
                    mod.aspect_x = res_x
                    mod.aspect_y = res_y

                print(f"Added UV Project modifier to {mesh_obj.name} using camera '{camera.name}'")

            def get_active_movie_clip():
                """
                Attempts to find the movie clip currently open in the Motion Tracking Editor.
                """
                # Method 1: Check direct context (works if script is run via a button in the Tracker)
                if getattr(bpy.context, "edit_movieclip", None):
                    return bpy.context.edit_movieclip

                # Method 2: Iterate through screen areas (works if running from Scripting tab)
                for area in bpy.context.screen.areas:
                    if area.type == 'CLIP_EDITOR':
                        space = area.spaces.active
                        if space and space.clip:
                            return space.clip

                return None

            def apply_active_clip_material(obj):
                # 1. Get the target object

                # 2. Get the ACTIVE Clip
                clip = get_active_movie_clip()

                if not clip:
                    print("Error: No video is currently open in the Motion Tracking Editor.")
                    return None

                print(f"Found Active Clip: {clip.name}")

                # 3. Prepare the Material
                mat_name = f"Mat_{clip.name}"
                mat = bpy.data.materials.get(mat_name)
                if not mat:
                    mat = bpy.data.materials.new(name=mat_name)

                mat.use_nodes = True
                nodes = mat.node_tree.nodes
                links = mat.node_tree.links
                nodes.clear()

                # 4. Create Shader Nodes
                node_out = nodes.new('ShaderNodeOutputMaterial')
                node_out.location = (400, 0)

                node_emit = nodes.new('ShaderNodeEmission')
                node_emit.location = (200, 0)

                node_tex = nodes.new('ShaderNodeTexImage')
                node_tex.location = (-100, 0)
                node_tex.label = clip.name

                # 5. Load/Link the Clip to the Image Node
                image_block = None

                # Check existing images for matching filepath
                for img in bpy.data.images:
                    if img.filepath == clip.filepath:
                        image_block = img
                        break

                # If not found, load it from the clip's path
                if not image_block:
                    try:
                        image_block = bpy.data.images.load(clip.filepath)
                    except RuntimeError:
                        print(f"Error: Could not load file from '{clip.filepath}'")
                        return mat

                node_tex.image = image_block

                # 6. Sync Animation Settings
                node_tex.image_user.use_auto_refresh = True
                node_tex.image_user.frame_duration = clip.frame_duration
                node_tex.image_user.frame_start = clip.frame_start
                node_tex.image_user.frame_offset = clip.frame_offset
                node_tex.extension = 'EXTEND'

                # 7. Add UV Map Node
                node_uv = nodes.new('ShaderNodeUVMap')
                node_uv.location = (-300, 0)
                node_uv.uv_map = "Projected_UV"  # Note: Ensure your mesh generates this UV if needed

                # 8. Link Everything
                links.new(node_uv.outputs['UV'], node_tex.inputs['Vector'])
                links.new(node_tex.outputs['Color'], node_emit.inputs['Color'])
                links.new(node_emit.outputs['Emission'], node_out.inputs['Surface'])

                # 9. Assign to Object
                if obj.data.materials:
                    obj.data.materials[0] = mat
                else:
                    obj.data.materials.append(mat)
                return mat

            def create_tracks_node_tree(obj, applied_material):
                """
                Creates the Geometry Nodes modifier and tree based on the reference image,
                including the position-based geometry deletion logic.
                """
                modifier_name = "Surface Generator"
                mod = obj.modifiers.get(modifier_name)
                if not mod:
                    mod = obj.modifiers.new(name=modifier_name, type='NODES')

                tree_name = "SurfaceGenerator_Nodes"
                if mod.node_group:
                    node_tree = mod.node_group
                    node_tree.nodes.clear()
                else:
                    node_tree = bpy.data.node_groups.new(name=tree_name, type='GeometryNodeTree')
                    mod.node_group = node_tree

                nodes = node_tree.nodes
                links = node_tree.links

                for item in node_tree.interface.items_tree:
                    node_tree.interface.remove(item)

                in_geo = node_tree.interface.new_socket(name="Geometry", in_out='INPUT',
                                                        socket_type='NodeSocketGeometry')
                in_res = node_tree.interface.new_socket(name="Resolution", in_out='INPUT', socket_type='NodeSocketInt')
                in_res.default_value = 100
                in_res.min_value = 1
                in_rad = node_tree.interface.new_socket(name="Connection Radius", in_out='INPUT',
                                                        socket_type='NodeSocketFloat')
                in_rad.default_value = 2.0
                in_rad.min_value = 0.0

                out_geo = node_tree.interface.new_socket(name="Geometry", in_out='OUTPUT',
                                                         socket_type='NodeSocketGeometry')

                n_input = nodes.new('NodeGroupInput')
                n_input.location = (-900, 0)

                # -- Group Output
                n_output = nodes.new('NodeGroupOutput')
                n_output.location = (1400, 0)

                # -- Position Node
                n_position = nodes.new('GeometryNodeInputPosition')
                n_position.location = (-900, 200)

                # -- Vector Math (Length)
                n_length = nodes.new('ShaderNodeVectorMath')
                n_length.location = (-700, 200)
                n_length.operation = 'LENGTH'

                # -- Compare (Greater Than)
                n_compare = nodes.new('FunctionNodeCompare')
                n_compare.location = (-500, 200)
                n_compare.operation = 'GREATER_THAN'
                n_compare.data_type = 'FLOAT'
                n_compare.inputs[1].default_value = 100.00

                # -- Delete Geometry
                n_del_geo = nodes.new('GeometryNodeDeleteGeometry')
                n_del_geo.location = (-500, 0)
                n_del_geo.domain = 'POINT'

                # -- Points to Volume
                n_pts_to_vol = nodes.new('GeometryNodePointsToVolume')
                n_pts_to_vol.location = (-300, 100)
                if hasattr(n_pts_to_vol, 'resolution_mode'):
                    n_pts_to_vol.resolution_mode = 'VOXEL_AMOUNT'
                if 'Density' in n_pts_to_vol.inputs:
                    n_pts_to_vol.inputs['Density'].default_value = 3.4

                # -- Volume to Mesh
                n_vol_to_mesh = nodes.new('GeometryNodeVolumeToMesh')
                n_vol_to_mesh.location = (-100, 200)
                if hasattr(n_vol_to_mesh, 'resolution_mode'):
                    n_vol_to_mesh.resolution_mode = 'GRID'
                if 'Threshold' in n_vol_to_mesh.inputs:
                    n_vol_to_mesh.inputs['Threshold'].default_value = 0.1
                if 'Adaptivity' in n_vol_to_mesh.inputs:
                    n_vol_to_mesh.inputs['Adaptivity'].default_value = 0.0

                # -- Realize Instances
                n_realize = nodes.new('GeometryNodeRealizeInstances')
                n_realize.location = (100, 200)

                # -- Geometry Proximity
                n_proximity = nodes.new('GeometryNodeProximity')
                n_proximity.location = (-100, -100)
                n_proximity.target_element = 'POINTS'

                # -- Set Position
                n_set_pos = nodes.new('GeometryNodeSetPosition')
                n_set_pos.location = (300, 0)

                # -- Set Material
                n_set_mat = nodes.new('GeometryNodeSetMaterial')
                n_set_mat.location = (500, 0)
                if applied_material:
                    n_set_mat.inputs[2].default_value = applied_material

                # -- Merge by Distance
                n_merge = nodes.new('GeometryNodeMergeByDistance')
                n_merge.location = (700, 0)
                if hasattr(n_merge, 'mode'):
                    n_merge.mode = 'ALL'
                n_merge.inputs['Distance'].default_value = 0.001

                # Position -> Vector Length
                links.new(n_position.outputs['Position'], n_length.inputs['Vector'])

                # Vector Length -> Compare (A)
                links.new(n_length.outputs['Value'], n_compare.inputs['A'])  # Float A

                # Compare Result -> Delete Geometry Selection
                links.new(n_compare.outputs['Result'], n_del_geo.inputs['Selection'])

                # Group Input (Geometry) -> Delete Geometry
                links.new(n_input.outputs['Geometry'], n_del_geo.inputs['Geometry'])

                # Delete Geometry -> Points to Volume
                links.new(n_del_geo.outputs['Geometry'], n_pts_to_vol.inputs['Points'])

                # Parameter inputs still come directly from Group Input
                links.new(n_input.outputs['Resolution'], n_pts_to_vol.inputs['Voxel Amount'])
                links.new(n_input.outputs['Connection Radius'], n_pts_to_vol.inputs['Radius'])

                # Points to Volume -> Volume to Mesh
                links.new(n_pts_to_vol.outputs['Volume'], n_vol_to_mesh.inputs['Volume'])

                # Volume to Mesh -> Realize Instances
                links.new(n_vol_to_mesh.outputs['Mesh'], n_realize.inputs['Geometry'])

                # Realize Instances -> Set Position
                links.new(n_realize.outputs['Geometry'], n_set_pos.inputs['Geometry'])

                # Delete Geometry (was Group Input) -> Geometry Proximity (Target)
                links.new(n_del_geo.outputs['Geometry'], n_proximity.inputs['Target'])

                # Geometry Proximity (Position) -> Set Position (Position)
                links.new(n_proximity.outputs['Position'], n_set_pos.inputs['Position'])

                # Set Position -> Set Material
                links.new(n_set_pos.outputs['Geometry'], n_set_mat.inputs['Geometry'])

                # Set Material -> Merge by Distance
                links.new(n_set_mat.outputs['Geometry'], n_merge.inputs['Geometry'])

                # Merge by Distance -> Output
                links.new(n_merge.outputs['Geometry'], n_output.inputs['Geometry'])

                # 6. Apply Default Values to Modifier Instance
                mod[in_res.identifier] = 300
                mod[in_rad.identifier] = 0.2

            def delete_old_track_object():
                base_name = "PointCloudSurface"
                current_scene = bpy.context.scene
                objs_to_delete = [
                    obj for obj in current_scene.objects
                    if obj.name == base_name or obj.name.startswith(base_name + ".")
                ]
                for obj in objs_to_delete:
                    bpy.data.objects.remove(obj, do_unlink=True)

            def create_pointcloud():
                bpy.context.space_data.show_disabled = True
                bpy.ops.clip.select_all(action='SELECT')

                bpy.ops.clip.bundles_to_mesh()
                bpy.context.space_data.show_disabled = False
                tracker_mesh = bpy.context.active_object
                return tracker_mesh

            delete_old_track_object()
            global tracker_mesh
            tracker_mesh = create_pointcloud()
            generated_material = apply_active_clip_material(tracker_mesh)
            create_tracks_node_tree(tracker_mesh, generated_material)
            apply_camera_projection(tracker_mesh)
            tracker_mesh.name = "PointCloudSurface"
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


# Check for updates button
class CheckForUpdates(bpy.types.Operator):
    bl_idname = "autotrack.checkforupdates"
    bl_label = "Check For Updates..."
    bl_description = "Automatically checks for updates on the Blender Extensions platform"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            bpy.ops.extensions.repo_sync(repo_index=0)
            bpy.ops.extensions.package_install(pkg_id="siemen_lens_blender_autotrack", repo_index=0)
            self.report({'INFO'}, f"Add-On is now up-to-date!")
            return {'FINISHED'}
        except Exception as e:
            self.report({'WARNING'}, f"Add-On failed to update. {e}")
            return {'CANCELLED'}


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
            try:
                row.label(text=f"AutoTrack v4.0.2", icon='TRACKER')
            except:
                pass
            row = box.row()
            row.alignment = 'CENTER'
            row.label(text="Created by Siemen Lens")
            row = box.row()
            row.alignment = 'CENTER'
            row.operator("autotrack.checkforupdates", icon='FILE_REFRESH')
            row.scale_y = 0.85
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
            if context.scene.at_is_finished:
                resultsbox = layout.box()
                resultsbox.scale_y = 1
                resultsbox.label(text=context.scene.at_result_message, icon="INFO")
                layout.separator()

            # if it's not running, we should display the options and parameters
            if not context.scene.at_is_running:
                if clip:
                    scenebox = layout.box()
                    scenebox.label(text="Scene Settings", icon="VIEW_CAMERA")
                    scenebox.prop(context.scene, "option_setsceneframe")
                    if not context.scene.option_setsceneframe:
                        row = scenebox.row()
                        row.prop(context.scene, "frame_start", text="Begin")
                        row.prop(context.scene, "frame_end", text="End")
                    scenebox.prop(context.scene, "option_tripod")
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
                            if annotation and clip:
                                markerboxrow = markerbox.row()
                                markerboxrow.prop(context.scene, "option_annotation")
                                if context.scene.option_annotation:
                                    markerboxrow.prop(context.scene, "option_annotation_mode")
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
                    if context.scene.at_is_finished and clip and cam:
                        layout.separator()
                        generatesurfacebox = layout.box()
                        generatesurfacebox.label(text="Surface Generator Settings", icon='OUTLINER_DATA_SURFACE')
                        generatesurfacebox.operator("autotrack.generatesurface")
                        try:
                            mod = tracker_mesh.modifiers.get("Surface Generator")
                            generatesurfacebox.prop(mod, '["Socket_1"]', text="Resolution")
                            generatesurfacebox.prop(mod, '["Socket_2"]', text="Connection Radius")
                        except: pass
                else:
                    box = layout.box()
                    row = box.row()
                    row.alignment = 'CENTER'
                    row.alert = True
                    row.label(text="Welcome to AutoTrack!", icon='TRACKER')
                    row2 = box.row()
                    row2.alignment = 'CENTER'
                    row2.label(text="Import a video to get started.")
                    box.operator("clip.open", icon='FILE_MOVIE')

                if clip:
                    layout.separator()
                    starttrackingrow = layout.row()
                    starttrackingrow.scale_y = 2  # make the start button taller
                    starttrackingrow.alert = True  # color the start button red
                    starttrackingrow.operator("autotrack.runtracking", icon='CON_FOLLOWTRACK')
                    layout.separator()

            # if AutoTrack is running, we should display a progress bar and status message instead of our parameters.
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
                        warningbox.label(text=context.scene.at_warning, icon='WARNING_LARGE')
                layout.separator()
                box = layout.box()
                box.alert = True  # color the progress bar red
                box.scale_y = 1.5  # make the progress bar taller, more visible
                box.label(text=context.scene.at_status, icon="CON_FOLLOWTRACK")
                box.prop(context.scene, "at_progress", text="Progress", slider=True)
                layout.separator()
                layout.label(text=context.scene.at_remainingtime, icon="SORTTIME")
                warningrow = layout.row()
                warningrow.alert = True
                warningrow.label(text="Blender may freeze. Do not touch", icon="FREEZE")


# classes definition
classes = (
    Runtracking,
    QuickResolve,
    UIPanel,
    TestMarkers,
    ClearGreasePencil,
    GenerateSurface,
    AboutOpen,
    AboutClose,
    CheckForUpdates
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()