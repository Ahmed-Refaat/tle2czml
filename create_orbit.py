# this module contains classes and scripts for generating the .czml files used to visualize the satellites orbits

from czml_update import czml
from dateutil import parser
import ephem, os, math, pytz, datetime
from ephem import degrees
from sgp4.io import twoline2rv
from sgp4.earth_gravity import wgs72


BILLBOARD_SCALE = 1.5
SATELITE_IMAGE_URI = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAADJSURBVDhPnZHRDcMgEEMZjVEYpaNklIzSEfLfD4qNnXAJSFWfhO7w2Zc0Tf9QG2rXrEzSUeZLOGm47WoH95x3Hl3jEgilvDgsOQUTqsNl68ezEwn1vae6lceSEEYvvWNT/Rxc4CXQNGadho1NXoJ+9iaqc2xi2xbt23PJCDIB6TQjOC6Bho/sDy3fBQT8PrVhibU7yBFcEPaRxOoeTwbwByCOYf9VGp1BYI1BA+EeHhmfzKbBoJEQwn1yzUZtyspIQUha85MpkNIXB7GizqDEECsAAAAASUVORK5CYII="
LABEL_FONT = "11pt Lucida Console"

MULTIPLIER = 60
DESCRIPTION_TEMPLATE = 'Orbit of Satellite: '
MINUTES_IN_DAY = 1440
TIME_STEP = 300

DEFAULT_RGBA = [213, 255, 0, 255]
DEBUGGING = False

class Satellite:
	'Common base class for all satellites'

	def __init__(self, raw_tle, tle_object, rgba):
		self.raw_tle = raw_tle
		self.tle_object = tle_object  # sgp4Object
		self.rgba = rgba
		self.sat_name = raw_tle[0].rstrip()	
		self.orbital_time_in_minutes = (24.0/float(self.raw_tle[2][52:63]))*60.0
		self.tle_epoch = tle_object.epoch
		
	def getSatelliteName(self):
		return self.satName
		
class Colors:
	def __init__(self):
		colors_file = open('rgba_list.txt', 'r')
	
		rgbs = []
	
		for color in colors_file:
			rgb = color.split()
			rgb.append(255)  # append value for alpha
			rgbs.append(rgb)
		
		self.rgbs = rgbs
		self.index = 0
	
	def get_next_color(self):
		next_color = self.rgbs[self.index]
		if self.index < len(self.rgbs) - 1:
			self.index += 1
		else:
			self.index = 0
			
		return next_color

class OverPass:
	def __init__(self, info, sat, observer):
		self.rise_time = parser.parse(str(info[0])).replace(tzinfo=pytz.UTC)
		self.rise_azimuth = degrees(info[1])
		self.max_altitude_time = parser.parse(str(info[2])).replace(tzinfo=pytz.UTC)
		self.max_altitude = degrees(info[3])
		self.set_time = parser.parse(str(info[4])).replace(tzinfo=pytz.UTC)
		self.set_azimuth = degrees(info[5])
		self.duration = int((info[4] - info[0]) *60*60*24)

		self.observer = observer
		self.sat = sat
		self.sun = ephem.Sun()
		self.visible = self.check_visibility()



	def check_visibility(self):
		self.observer.date = self.max_altitude_time
		self.sun.compute(self.observer)
		self.sat.compute(self.observer)

		if degrees('-30:00:00') < degrees(self.sun.alt) < degrees('-6:00:00') and self.max_altitude:
			return True
		else:
			return False		
		
		
# create CZML doc with default document packet
def create_czml_file(sim_start_time, sim_end_time):
	interval = getInterval(sim_start_time, sim_end_time)
	doc = czml.CZML()
	packet1 = czml.CZMLPacket(id='document', version='1.0')
	packet1.clock = {"interval":interval,"currentTime":sim_start_time.isoformat(),"multiplier":MULTIPLIER,"range":"LOOP_STOP","step":"SYSTEM_CLOCK_MULTIPLIER"}
	doc.packets.append(packet1)
	
	return doc
	

def create_satellite_packet(satId, tle, orbitTimeInMinutes, simStartTime, simEndTime, rgba):
	availability = getInterval(simStartTime, simEndTime)

	packet = czml.CZMLPacket(id='Satellite/' + satId)
	packet.availability = availability
	packet.description = czml.Description(DESCRIPTION_TEMPLATE + ' ' + satId)
	packet.billboard = create_bill_board()
	packet.label = create_label(satId, rgba)
	packet.path = create_path(availability, orbitTimeInMinutes, rgba)
	packet.position = create_position(simStartTime, simEndTime, tle)  # have seperate arg for epoch incase for when you to start propagating from a time other than the tle epoch
	return packet	


def create_bill_board():
	bb = czml.Billboard(scale=BILLBOARD_SCALE, show=True)
	bb.image = SATELITE_IMAGE_URI
	return bb

def create_label(satId, rgba):
	lab = czml.Label(text=satId, show=True)
	
	lab.fillColor = {"rgba":rgba}
	lab.font = LABEL_FONT
	lab.horizontalOrigin = "LEFT"
	lab.outlineColor = {"rgba":[0,0,0,255]}
	lab.outlineWidth = 2	 
	lab.pixelOffset = {"cartesian2":[12,0]} 
	lab.style = 'FILL_AND_OUTLINE'
	lab.verticalOrigin = 'CENTER'
	return lab
	
	
def create_path(totalPathInterval, orbitTimeInMinutes, rgba):
	p = czml.Path()
	p.show = [{"interval":totalPathInterval, "boolean":True}]

	p.width = 1
	p.material = {"solidColor":{"color":{"rgba":rgba}}}
	p.resolution = 120

	startEpochStr = totalPathInterval.split("/")[0]
	endEpochStr = totalPathInterval.split("/")[1]
	
	leftOverMinutes = MINUTES_IN_DAY % orbitTimeInMinutes 
	numberOfFullOrbits = math.floor(MINUTES_IN_DAY/orbitTimeInMinutes)
	
	
	subPathIntervalStart = parser.parse(startEpochStr)
	subPathIntervalEnd = subPathIntervalStart + datetime.timedelta(minutes = leftOverMinutes)    # first interval roughly half an orbit, rest of the path intervals are full orbits
	
	subPathIntervalStr = subPathIntervalStart.isoformat() + '/' + subPathIntervalEnd.isoformat()
	orbitalTimeInSeconds = (orbitTimeInMinutes * 60.0)
	
	if DEBUGGING:
		print('Total Path Interval: ' + totalPathInterval)   # goes from tle epoch to 12/24 hours in future
	
	LT = []
	
	endEpoch = parser.parse(endEpochStr)
	
	for i in range(0, numberOfFullOrbits + 1):
		LT.append({
				  "interval":subPathIntervalStr,
				  "epoch":subPathIntervalStart.isoformat(),
				  "number":[
					0,orbitalTimeInSeconds,
					orbitalTimeInSeconds,0
				  ]
				})
			
		if DEBUGGING:
			print('Sub interval string: ' + subPathIntervalStr)
			
		subPathIntervalStart = subPathIntervalEnd
		subPathIntervalEnd = subPathIntervalStart + datetime.timedelta(minutes = orbitTimeInMinutes)
		
		subPathIntervalStr = subPathIntervalStart.isoformat() + '/' + subPathIntervalEnd.isoformat()
	
	if DEBUGGING:
		print()
	
	subPathIntervalStart = parser.parse(startEpochStr)
	subPathIntervalEnd = subPathIntervalStart + datetime.timedelta(minutes = leftOverMinutes)   # first interval roughly half an orbit, rest of the path intervals are full orbits
	
	subPathIntervalStr = subPathIntervalStart.isoformat() + '/' + subPathIntervalEnd.isoformat()	
	
	TT = []
	
	for i in range(0,numberOfFullOrbits + 1):
		TT.append({
				  "interval":subPathIntervalStr,
				  "epoch":subPathIntervalStart.isoformat(),
				  "number":[
					0,0,
					orbitalTimeInSeconds,orbitalTimeInSeconds
				  ]
				})	

		if DEBUGGING:
			print('Sub interval string: ' + subPathIntervalStr)			

		subPathIntervalStart = subPathIntervalEnd
		subPathIntervalEnd = subPathIntervalStart + datetime.timedelta(minutes = orbitTimeInMinutes)
		
		subPathIntervalStr = subPathIntervalStart.isoformat() + '/' + subPathIntervalEnd.isoformat()	

	p.leadTime = LT
	p.trailTime = TT	
	
	return p


def create_position(start_time, end_time, tle):
	pos = czml.Position()
	pos.interpolationAlgorithm = "LAGRANGE"
	pos.interpolationDegree = 5
	pos.referenceFrame = "INERTIAL"
	pos.epoch = start_time.isoformat()
	
	diff = end_time - start_time
	numberOfPositions = int(diff.total_seconds()/300)   
	numberOfPositions +=5;  # so that there's more than one position

	pos.cartesian = get_future_sat_positions(tle, numberOfPositions, start_time)

	return pos	


def getInterval(currentTime, endTime):
	return currentTime.isoformat() + "/" + endTime.isoformat()
	
def get_future_sat_positions(satTle, numberOfPositions, startTime):

	timeStep = 0
	output = []
	epoch = startTime
	for i in range(0, numberOfPositions):
		currentTime = startTime + datetime.timedelta(seconds=timeStep)
		eciPosition, eciVelocity = satTle.propagate(currentTime.year, currentTime.month, currentTime.day, currentTime.hour, currentTime.minute, currentTime.second)
	
		output.append(timeStep)
		output.append(eciPosition[0] * 1000)  # converts km's to m's are stores them in array
		output.append(eciPosition[1] * 1000)
		output.append(eciPosition[2] * 1000)
		timeStep += TIME_STEP
	
	return output
	
def get_satellite_orbit(raw_tle, sim_start_time, sim_end_time, czml_file_name):
	sat_name = raw_tle[0]
	tle_sgp4 = twoline2rv(raw_tle[1], raw_tle[2], wgs72)

	sat = Satellite(raw_tle, tle_sgp4, DEFAULT_RGBA)

	doc = create_czml_file(sim_start_time, sim_end_time)
	
	if DEBUGGING:
		print()
		print('Satellite Name: ', sat.satName)
		print('TLE Epoch: ', sat.tleEpoch)
		print('Orbit time in Minutes: ', sat.orbitalTimeInMinutes)	
		print()
	
	sat_packet = create_satellite_packet(sat.sat_name, sat.tle_object, sat.orbital_time_in_minutes, sim_start_time, sim_end_time, sat.rgba)
	doc.packets.append(sat_packet)
	doc.write(czml_file_name)		

		
#############################################################################
# running module from command line

def read_tles(tle_file_name, rgbs):
	tle_src = open(tle_file_name, 'r')
	raw_tle = []
	sats = []

	i = 1
	for line in tle_src:
		raw_tle.append(line)
		
		if i % 3 == 0:
			tle_object = twoline2rv(raw_tle[1], raw_tle[2], wgs72)
			sats.append(Satellite(raw_tle, tle_object, rgbs.get_next_color()))
			raw_tle = []
		
		i+=1
	
	return sats		


def get_latest_epoch(sats):
	latest = sats[0] 
	for sat in sats:
		if sat.tle_epoch > latest.tle_epoch:
			latest = sat
	return latest.tle_epoch

def get_earliest_epoch(sats):
	earliest = sats[0] 
	for sat in sats:
		if sat.tle_epoch < earliest.tle_epoch:
			earliest = sat
	return earliest.tle_epoch

def main():
	rgbs = Colors()
	satellite_array = read_tles('tle.txt', rgbs)
	
	sim_start_time = get_earliest_epoch(satellite_array)
	sim_end_time = get_latest_epoch(satellite_array)

	doc = create_czml_file(sim_start_time, sim_end_time)
	file_name = 'test.czml'

	for sat in satellite_array:
		sat_name = sat.sat_name
		orbit_time_in_minutes = sat.orbital_time_in_minutes
		tle_epoch = sat.tle_epoch

		print()
		print('Satellite Name: ', sat_name)
		print('TLE Epoch: ', tle_epoch)
		print('Orbit time in Minutes: ', orbit_time_in_minutes)	
		print()
		
		# version of method deprecated
		sat_packet = create_satellite_packet(sat.sat_name, sat.tle_object, sat.orbital_time_in_minutes, sim_start_time, sim_end_time, sat.rgba)

		doc.packets.append(sat_packet)

	doc.write(file_name)

if __name__ == '__main__':
	main()