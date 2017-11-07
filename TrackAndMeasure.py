import os
import errno
from ij import IJ, ImagePlus, ImageStack
from ij import WindowManager
from ij.gui import WaitForUserDialog
from ij.gui import OvalRoi, Roi
from ij.plugin.frame import RoiManager
from ij.plugin import ChannelSplitter   

def run():

	# ensure no other windows are open and clear resultstable
	IJ.run("Close All")
	IJ.run("Clear Results", "")
	#Ask user for file to be converted
	srcDir=IJ.getFilePath("Select file to analyse")
	if not srcDir:
		return
	
	#open file
	IJ.open(srcDir)
	dstDir = os.path.dirname(srcDir)
	print("dstDir = "+dstDir)
	#open ROI manager, save ROI names as labels in measurements
	rm = RoiManager.getInstance()
	if not rm:
		rm = RoiManager()
	rm.runCommand("UseNames", "true")

	# set parameters to be measured
	IJ.run("Set Measurements...", "area mean integrated limit display redirect=None decimal=3")

	FOVlist = WindowManager.getIDList()
	chnls = IJ.getString("Please enter which channels you would like to analyse. Example: 123 analyses channels 1, 2 and 3", '123')
	
	for FOV in FOVlist:
		imp = WindowManager.getImage(FOV)
		IJ.run(imp, "Arrange Channels...", "new="+chnls)
		imp.close()
		imp2 = WindowManager.getCurrentImage()

		imageTitle = WindowManager.getImage(FOV).getTitle()
		newDir = imageTitle + ' ROIs'

		dirPath = os.path.join(dstDir, newDir)

		if not os.path.exists(dirPath):
			try:
				os.makedirs(dirPath)		
			except OSError as e:
					if e.errno != errno.EEXIST:
						raise
		# clear ROI list before analysis
		rm.runCommand(imp2,"Deselect")
		rm.runCommand(imp2,"Delete")

		TMdata, nFrames = runTrackMate(imp2)
		if TMdata:
			iterateCoords(TMdata, nFrames, dirPath, imp2)
		imp2.changes = 0
		imp2.close()
	#relabel()
	resultsDir = os.path.splitext(srcDir)[0]+".csv"
	#while os.path.exists(resultsDir):
		#resultsDir = resultsDir+"_1"+".csv"
	IJ.saveAs("Results", resultsDir)
	

def runTrackMate(imp):
	import fiji.plugin.trackmate.Settings as Settings
	import fiji.plugin.trackmate.Model as Model
	import fiji.plugin.trackmate.SelectionModel as SelectionModel
	import fiji.plugin.trackmate.TrackMate as TrackMate
	import fiji.plugin.trackmate.Logger as Logger
	import fiji.plugin.trackmate.detection.DetectorKeys as DetectorKeys
	import fiji.plugin.trackmate.detection.DogDetectorFactory as DogDetectorFactory
	import fiji.plugin.trackmate.tracking.sparselap.SparseLAPTrackerFactory as SparseLAPTrackerFactory
	import fiji.plugin.trackmate.tracking.LAPUtils as LAPUtils
	import fiji.plugin.trackmate.visualization.hyperstack.HyperStackDisplayer as HyperStackDisplayer
	import fiji.plugin.trackmate.features.FeatureFilter as FeatureFilter
	import fiji.plugin.trackmate.features.FeatureAnalyzer as FeatureAnalyzer
	import fiji.plugin.trackmate.features.spot.SpotContrastAndSNRAnalyzerFactory as SpotContrastAndSNRAnalyzerFactory
	import fiji.plugin.trackmate.action.ExportStatsToIJAction as ExportStatsToIJAction
	import fiji.plugin.trackmate.io.TmXmlReader as TmXmlReader
	import fiji.plugin.trackmate.action.ExportTracksToXML as ExportTracksToXML
	import fiji.plugin.trackmate.io.TmXmlWriter as TmXmlWriter
	import fiji.plugin.trackmate.features.ModelFeatureUpdater as ModelFeatureUpdater
	import fiji.plugin.trackmate.features.SpotFeatureCalculator as SpotFeatureCalculator
	import fiji.plugin.trackmate.features.spot.SpotContrastAndSNRAnalyzer as SpotContrastAndSNRAnalyzer
	import fiji.plugin.trackmate.features.spot.SpotIntensityAnalyzerFactory as SpotIntensityAnalyzerFactory
	import fiji.plugin.trackmate.features.track.TrackSpeedStatisticsAnalyzer as TrackSpeedStatisticsAnalyzer
	import fiji.plugin.trackmate.util.TMUtils as TMUtils
	import fiji.plugin.trackmate.visualization.trackscheme.TrackScheme as TrackScheme
	import fiji.plugin.trackmate.visualization.PerTrackFeatureColorGenerator as PerTrackFeatureColorGenerator
  
	#-------------------------
	# Instantiate model object
	#-------------------------
	
	nFrames = imp.getNFrames() 
	model = Model()
	   
	# Set logger
	#model.setLogger(Logger.IJ_LOGGER)
	   
	#------------------------
	# Prepare settings object
	#------------------------
	      
	settings = Settings()
	settings.setFrom(imp)
	      
	# Configure detector
	settings.detectorFactory = DogDetectorFactory()
	settings.detectorSettings = {
	    DetectorKeys.KEY_DO_SUBPIXEL_LOCALIZATION : True,
	    DetectorKeys.KEY_RADIUS : 12.30,
	    DetectorKeys.KEY_TARGET_CHANNEL : 1,
	    DetectorKeys.KEY_THRESHOLD : 100.,
	    DetectorKeys.KEY_DO_MEDIAN_FILTERING : False,
	} 
	    
	# Configure tracker
	settings.trackerFactory = SparseLAPTrackerFactory()
	settings.trackerSettings = LAPUtils.getDefaultLAPSettingsMap()
	settings.trackerSettings['LINKING_MAX_DISTANCE'] = 10.0
	settings.trackerSettings['GAP_CLOSING_MAX_DISTANCE']=10.0
	settings.trackerSettings['MAX_FRAME_GAP']= 3
	   
	# Add the analyzers for some spot features.
	# You need to configure TrackMate with analyzers that will generate 
	# the data you need. 
	# Here we just add two analyzers for spot, one that computes generic
	# pixel intensity statistics (mean, max, etc...) and one that computes
	# an estimate of each spot's SNR. 
	# The trick here is that the second one requires the first one to be in
	# place. Be aware of this kind of gotchas, and read the docs. 
	settings.addSpotAnalyzerFactory(SpotIntensityAnalyzerFactory())
	settings.addSpotAnalyzerFactory(SpotContrastAndSNRAnalyzerFactory())
	   
	# Add an analyzer for some track features, such as the track mean speed.
	settings.addTrackAnalyzer(TrackSpeedStatisticsAnalyzer())
	   
	settings.initialSpotFilterValue = 1
	   
	print(str(settings))
	      
	#----------------------
	# Instantiate trackmate
	#----------------------
	   
	trackmate = TrackMate(model, settings)
	      
	#------------
	# Execute all
	#------------ 
	     
	ok = trackmate.checkInput()
	if not ok:
	    sys.exit(str(trackmate.getErrorMessage()))
	     
	ok = trackmate.process()
	if not ok:
	    sys.exit(str(trackmate.getErrorMessage()))
 
	#----------------
	# Display results
	#----------------
	    
	selectionModel = SelectionModel(model)
	displayer =  HyperStackDisplayer(model, selectionModel, imp)
	displayer.render()
	displayer.refresh()

	#---------------------
	# Select correct spots
	#---------------------

	# Prepare display.
	sm = SelectionModel(model)
	color = PerTrackFeatureColorGenerator(model, 'TRACK_INDEX')	  

	# launch TrackScheme to select spots and tracks
	trackscheme = TrackScheme(model, sm)
	trackscheme.setDisplaySettings('TrackColoring', color)
	trackscheme.render()
	  
	# Update image with TrackScheme commands
	view = HyperStackDisplayer(model, sm, imp)
	view.setDisplaySettings('TrackColoring', color)
	view.render()

	# Wait for the user to select correct spots and tracks before collecting data
	dialog = WaitForUserDialog("Spots","Delete incorrect spots and edit tracks if necessary. (Press ESC to cancel analysis)")	
	dialog.show()
	if dialog.escPressed():
		IJ.run("Remove Overlay", "")
		imp.close()
		return ([], nFrames)

	# The feature model, that stores edge and track features.
	#model.getLogger().log('Found ' + str(model.getTrackModel().nTracks(True)) + ' tracks.')
	fm = model.getFeatureModel()
	crds_perSpot = []   
	for id in model.getTrackModel().trackIDs(True):
	   
	    # Fetch the track feature from the feature model.(remove """ to enable)
	    """v = fm.getTrackFeature(id, 'TRACK_MEAN_SPEED')
	    model.getLogger().log('')
	    model.getLogger().log('Track ' + str(id) + ': mean velocity = ' + str(v) + ' ' + model.getSpaceUnits() + '/' + model.getTimeUnits())"""
	    trackID = str(id)
	    track = model.getTrackModel().trackSpots(id)

	    spot_track = {}
	    for spot in track:
	        sid = spot.ID()
	        # Fetch spot features directly from spot. 
	        x=spot.getFeature('POSITION_X')
	        y=spot.getFeature('POSITION_Y')
	        t=spot.getFeature('FRAME')
	        q=spot.getFeature('QUALITY')
	        snr=spot.getFeature('SNR') 
	        mean=spot.getFeature('MEAN_INTENSITY')
	        #model.getLogger().log('\tspot ID = ' + str(sid) + ', x='+str(x)+', y='+str(y)+', t='+str(t)+', q='+str(q) + ', snr='+str(snr) + ', mean = ' + str(mean))
	        spot_track[t] = (x, y)
	    crds_perSpot.append(spot_track)
	    #print ("Spot", crds_perSpot.index(spot_track),"has the following coordinates:", crds_perSpot[crds_perSpot.index(spot_track)])
	return (crds_perSpot, nFrames)   

def createROI(xy_coord, diameter):
	imp = WindowManager.getCurrentImage()
	pixelWidth = imp.getCalibration().pixelWidth
	pixelHeight = imp.getCalibration().pixelHeight
	x_diameter = diameter/pixelWidth
	y_diameter = diameter/pixelHeight	
	x_coord = xy_coord[0]/pixelWidth-(0.5*x_diameter)
	y_coord = xy_coord[1]/pixelHeight-(0.5*y_diameter)
	
	rm = RoiManager.getInstance()
	if not rm:
		rm = RoiManager()
		
	roi = OvalRoi(x_coord, y_coord, x_diameter, y_diameter)
	rm.addRoi(roi)

def adjustRoiAndMeasure(imp, frameNumber, dstDir):
	
	rm = RoiManager.getInstance()
	if not rm:
		rm = RoiManager()

	nROIs = rm.getCount()
	indexlist = range(nROIs)
	
	if nROIs > 2:
		for roi in indexlist:
	
			indexlist_copy = list(indexlist)
			del indexlist_copy[roi]
			rm.setSelectedIndexes(indexlist_copy)
			rm.runCommand(imp,"Combine")
			IJ.run(imp, "Make Inverse", "")
			rm.addRoi(imp.getRoi())
			new_nROI = rm.getCount()
			rm.setSelectedIndexes([roi, new_nROI-1])
			rm.runCommand(imp,"AND")
			if imp.getRoi():
				rm.addRoi(imp.getRoi())
				rm.setSelectedIndexes([new_nROI])
				rm.runCommand("Rename", "Cell"+str(roi))
			else:
				rm.setSelectedIndexes([roi])
				rm.addRoi(imp.getRoi())
			rm.setSelectedIndexes([new_nROI-1])
			rm.runCommand(imp, "Delete")
	elif nROIs == 2:
		for roi in indexlist:
			indexlist_copy = list(indexlist)
			del indexlist_copy[roi]
			
			rm.setSelectedIndexes(indexlist_copy)
			IJ.run(imp, "Make Inverse", "")
			rm.addRoi(imp.getRoi())
			new_nROI = rm.getCount()
			rm.setSelectedIndexes([roi, new_nROI-1])
			rm.runCommand(imp,"AND")
			rm.addRoi(imp.getRoi())
			rm.setSelectedIndexes([new_nROI])
			rm.runCommand("Rename", "Cell"+str(roi))
			rm.setSelectedIndexes([new_nROI-1])
			rm.runCommand(imp, "Delete")
			
	elif nROIs == 1:
		new_nROI = nROIs
		rm.setSelectedIndexes([new_nROI])
		rm.runCommand("Rename", "Cell0")
		
	else:
		return
							
	adjustedROIs = range(nROIs, new_nROI,1)
	rm.setSelectedIndexes(adjustedROIs)
	measureChannels(adjustedROIs, imp, frameNumber) 
	rm.runCommand("Save selected", dstDir+"\\Frame "+str(frameNumber+1)+" roi set.zip")
	rm.runCommand(imp,"Deselect")
	rm.runCommand(imp,"Delete")
	
	
def iterateCoords(spotsData, n_Frames, path, imp):
	for i in xrange(n_Frames):
		imp.setSlice(i+1)
		for index, spotData in enumerate(spotsData):
			p = spotData.get(i)
			if p:
				createROI(p, 40)
		adjustRoiAndMeasure(imp, i, path)

def extractChannel(imp, nChannel, nFrame):
	""" Extract a stack for a specific color channel and time frame """
	imageTitle = imp.getTitle()
	delimiters = []
	if 'series' in imageTitle:
				delimiters.append(imageTitle.index('series'))
	try:
		series = "FOV"+imageTitle[(delimiters[0]+7):(delimiters[0]+9)]
	except IndexError:	
		series = "Series ?"
		
	stack = imp.getImageStack()
	ch = ImageStack(imp.width, imp.height)
	index = imp.getStackIndex(nChannel, 1, nFrame)
	ch.addSlice(str(1), stack.getProcessor(index))
	return ImagePlus(series+":Frame" + str(nFrame+1)+":C" + str(nChannel), ch)

def measureChannels(ROIset, imp, frameNumber):
	rm = RoiManager.getInstance()
	if not rm:
		rm = RoiManager()
	nChannels = imp.getNChannels()
	for channel in range(nChannels):
		target_imp = extractChannel(imp, channel+1, frameNumber)
		target_imp.show()
		for roi in ROIset:
			rm.setSelectedIndexes([roi])
			IJ.setAutoThreshold(target_imp, "Huang dark")
			rm.runCommand(target_imp, "Measure")
		target_imp.close()
		
def relabel():
	import re 
	from ij.measure import ResultsTable
	rt = ResultsTable.getResultsTable()
	nResults = rt.size()
	for result in range(nResults):
		oldLabel = rt.getLabel(result)
		delimiters = []
		keywords = ["series"]
		for keyword in keywords:
			if keyword in oldLabel:
				delimiters.append(oldLabel.index(keyword))
		
		channel = oldLabel[0:2]
		try:
			series = "FOV"+oldLabel[(delimiters[0]+7):(delimiters[0]+9)]
		except IndexError:	
			series = "FOV?"

		foundColons = [m.start() for m in re.finditer(':', oldLabel)]
		cell = oldLabel[foundColons[0]+1:foundColons[1]]
		
		newLabel = channel+"_"+series+"_"+cell
		rt.setLabel(newLabel, result)
	rt.show("Results")

run()

















