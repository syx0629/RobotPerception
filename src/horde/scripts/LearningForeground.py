#!/usr/bin/env python

"""
Author: David Quail, February, 2017.

Description:
LearningForeground contains a collection of GVF's. It accepts new state representations, learns, and then takes action.

"""


import rospy
import threading
import yaml

from std_msgs.msg import String
from std_msgs.msg import Int16
from std_msgs.msg import Float64

from dynamixel_driver.dynamixel_const import *

from diagnostic_msgs.msg import DiagnosticArray
from diagnostic_msgs.msg import DiagnosticStatus
from diagnostic_msgs.msg import KeyValue

from dynamixel_msgs.msg import MotorState
from dynamixel_msgs.msg import MotorStateList

from horde.msg import StateRepresentation

from BehaviorPolicy import *
from TileCoder import *
from GVF import *
from Verifier import *
from PredictLoadDemon import *
import time

import numpy

"""
sets up the subscribers and starts to broadcast the results in a thread every 0.1 seconds
"""

def directLeftPolicy(state):
    return 2

def atLeftGamma(state):
    if state.encoder >=1020.0:
        return 0
    else:
        return 1

def loadCumulant(state):
    return state.load

def timestepCumulant(state):
    return 1

def makeVectorBitCumulantFunction(bitIndex):
    def cumulantFunction(state):
        if (state.X[bitIndex] == 1):
            return 1
        else:
            return 0
    return cumulantFunction


def createPredictLoadGVFs():
    #GVFS that predict how much future load at different timesteps on and off policy
    #Create On policy GVFs for gamma values that correspond to timesteps: {1,2,3,4,5,6,7,8,9,10}.
    #Create Off policy GVFs for the same gamma values

    gvfs = []

    for i in range(1, 10, 1):
        #T = 1/(1-gamma)
        #gamma = (T-1)/T
        gamma = (i-1)/i

        #Create On policy gvf
        gvfOnPolicy = GVF(TileCoder.numberOfTiles*TileCoder.numberOfTiles * TileCoder.numberOfTilings, 0.1 / TileCoder.numberOfTilings, isOffPolicy = False, name = "PredictedLoadGamma" + str(i))
        gvfOnPolicy.gamma = gamma
        gvfOnPolicy.cumulant = loadCumulant

        gvfs.append(gvfOnPolicy)

        #Create Off policy gvf
        gvOffPolicy = GVF(TileCoder.numberOfTiles*TileCoder.numberOfTiles * TileCoder.numberOfTilings, 0.1 / TileCoder.numberOfTilings, isOffPolicy = True, name = "PredictedLoadGamma" + str(i))
        gvOffPolicy.gamma = gamma
        gvOffPolicy.cumulant = loadCumulant
        gvOffPolicy.policy = directLeftPolicy

        gvfs.append(gvOffPolicy)

    return gvfs

def createHowLongUntilLeftGVFs():
    #Create GVFs that predict how long it takes to get to the end. One on policy. And one off policy - going straight there.

    gvfs = []

    gvfOn = GVF(TileCoder.numberOfTiles*TileCoder.numberOfTiles * TileCoder.numberOfTilings, 0.1 / TileCoder.numberOfTilings, isOffPolicy = False, name = "HowLongLeftOnPolicy")
    gvfOn.gamma = atLeftGamma
    gvfOn.cumulant = timestepCumulant

    gvfs.append(gvfOn)

    gvfOff = GVF(TileCoder.numberOfTiles * TileCoder.numberOfTiles * TileCoder.numberOfTilings, 0.1 / TileCoder.numberOfTilings, isOffPolicy=True, name = "HowLongLeftOffPolicy")
    gvfOff.gamma = atLeftGamma
    gvfOff.cumulant = timestepCumulant
    gvfOff.policy = directLeftPolicy

    gvfs.append(gvfOff)

    return gvfs

def createNextBitGVFs():
    gvfs = []
    vectorSize = TileCoder.numberOfTiles * TileCoder.numberOfTiles * TileCoder.numberOfTilings
    for i in range(0, vectorSize, 1):
        gvfOn = GVF(TileCoder.numberOfTiles*TileCoder.numberOfTiles * TileCoder.numberOfTilings, 0.1 / TileCoder.numberOfTilings, isOffPolicy = False, name = "NextBitOnPolicy"+ str(i))
        gvfOn.cumulant = makeVectorBitCumulantFunction(i)
        gvfOn.gamma = 0
        gvfs.append(gvfOn)

        gvfOff = GVF(TileCoder.numberOfTiles * TileCoder.numberOfTiles * TileCoder.numberOfTilings, 0.1 / TileCoder.numberOfTilings, isOffPolicy=True, name = "NextBitOffPolicy"+ str(i))
        gvfOff.cumulant = makeVectorBitCumulantFunction(i)
        gvfOff.gamma = 0
        gvfOff.policy = directLeftPolicy
        gvfOff.append(gvfOff)

    return gvfs


class LearningForeground:

    def __init__(self):
        self.demons = []
        self.verifiers = {}

        self.behaviorPolicy = BehaviorPolicy()

        self.lastAction = 0

        self.currentRadians = 0
        self.increasingRadians = True

        """
        extremeLeftPrediction = GVF(TileCoder.numberOfTiles*TileCoder.numberOfTiles * TileCoder.numberOfTilings, 0.1 / TileCoder.numberOfTilings, False)
        extremeLeftPrediction.gamma = atLeftGamma
        self.demons.append(extremeLeftPrediction)
        extremeLeftVerifier = Verifier(4, 'StepsToExtremeLeft')

        self.verifiers[extremeLeftPrediction] = extremeLeftVerifier
        """

        """
        directLeftPrediction = GVF(TileCoder.numberOfTiles*TileCoder.numberOfTiles * TileCoder.numberOfTilings, 0.1/TileCoder.numberOfTilings, True)
        directLeftPrediction.policy = directLeftPolicy
        directLeftPrediction.gamma = atLeftGamma
        self.demons.append(directLeftPrediction)
        """

        """
        predictLoadPrediction = PredictLoadDemon(self.numTiles*self.numTiles*self.numTilings, 1.0/(10.0 * self.numTilings))
        predictLoadVerifier = Verifier(5)
        self.demons.append(predictLoadPrediction)
        self.verifiers.append(predictLoadVerifier)
        """
        self.demons = createHowLongUntilLeftGVFs()

        self.previousState = False

        #Initialize the sensory values of interest

    def performSlowBackAndForth(self):
        if self.increasingRadians:
            self.lastAction = 2
        else:
            self.lastAction = 1

        if (self.increasingRadians):
            self.currentRadians = self.currentRadians + 0.05
            if self.currentRadians >= 3.0:
                print("Switching direction!!!")
                self.increasingRadians = False
        else:
            self.currentRadians = self.currentRadians - 0.05
            if self.currentRadians <= 0.0:
                print("Switching direction!!!")
                self.increasingRadians = True

        print("Going to radians: " + str(self.currentRadians))
        pub = rospy.Publisher('tilt_controller/command', Float64, queue_size=10)
        pub.publish(self.currentRadians)

    def performAction(self, action):
        print("Performing action: "  + str(action))
        #Take the action and issue the actual dynamixel command
        pub = rospy.Publisher('tilt_controller/command', Float64, queue_size=10)

        if (action ==1):
            #Move left
            pub.publish(0.0)
        elif (action == 2):
            pub.publish(3.0)

        self.lastAction = action

    def updateDemons(self, newState):
        print("LearningForeground received stateRepresentation encoder: " + str(newState.encoder))

        encoderPosition = newState.encoder
        speed = newState.speed
        load = newState.load

        if self.previousState:
            #Learning
            for demon in self.demons:
                demon.learn(self.previousState, self.lastAction, newState)
                if demon in self.verifiers:
                    self.verifiers[demon].append(demon.gamma(newState), demon.cumulant(newState), demon.prediction(newState), newState)

            """
            action  = self.behaviorPolicy.policy(newState)
            self.performAction(action)
            """
            self.performSlowBackAndForth()

    def publishPredictions(self):
        print("Publishing predictions")


    def receiveStateUpdateCallback(self, newState):
        #Staterepresentation callback
        #Convert the list of X's into an actual numpy array
        newState.X = numpy.array(newState.X)
        newState.lastX = numpy.array(newState.lastX)
        self.updateDemons(newState)
        self.publishPredictions()
        self.previousState = newState

    def start(self):
        print("In Horde foreground start")
        # Subscribe to all of the relevent sensor information. To start, we're only interested in motor_states, produced by the dynamixels
        #rospy.Subscriber("observation_manager/servo_position", Int16, self.receiveObservationCallback)
        rospy.Subscriber("observation_manager/state_update", StateRepresentation, self.receiveStateUpdateCallback)

        rospy.spin()

if __name__ == '__main__':
    foreground = LearningForeground()
    #Set the mixels to 0
    rospy.init_node('horde_foreground', anonymous=True)
    pub = rospy.Publisher('tilt_controller/command', Float64, queue_size=10)
    pub.publish(0.0)

    time.sleep(3)

    foreground.start()


"""
motor_states:
  -
    timestamp: 1485931061.8
    id: 2
    goal: 805
    position: 805
    error: 0
    speed: 0
    load: 0.0
    voltage: 12.3
    temperature: 32
    moving: False
  -
    timestamp: 1485931061.8
    id: 3
    goal: 603
    position: 603
    error: 0
    speed: 0
    load: 0.0
    voltage: 12.3
    temperature: 34
    moving: False
"""