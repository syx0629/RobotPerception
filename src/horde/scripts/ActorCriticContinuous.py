import numpy
import rospy
from std_msgs.msg import Float64
from horde.msg import StateRepresentation
from TileCoder import *

class ActorCriticContinuous():
    def __init__(self):
        self.maxAction = 1023.0
        self.minAction = 510.0
        self.numberOfFeatures = TileCoder.numberOfTilings * TileCoder.numberOfTiles * TileCoder.numberOfTiles

        #Eligibility traces and weights
        #Value / Critic
        self.elibibilityTraceValue = numpy.zeros(self.numberOfFeatures)
        self.valueWeights = numpy.zeros(self.numberOfFeatures)

        #Mean
        self.elibibilityTraceMean = numpy.zeros(self.numberOfFeatures)
        self.policyWeightsMean = numpy.zeros(self.numberOfFeatures)

        #Deviation
        self.elibibilityTraceVariance = numpy.zeros(self.numberOfFeatures)
        self.policyWeightsVariance = numpy.zeros(self.numberOfFeatures)

        self.lambdaPolicy = 0.35
        self.lambdaValue = 0.35
        self.averageReward = 0.0

        self.stepSizeValue = 0.1
        self.stepSizeVariance = 0.01
        self.stepSizeMean = 10*self.stepSizeVariance
        self.rewardStep = 0.01

    def mean(self, state):
        m = numpy.inner(self.policyWeightsMean, state.X)
        return m

    def variance(self, state):
        v = numpy.exp(numpy.inner(self.policyWeightsVariance, state.X))
        return v

    def pickActionForState(self, state):

        print("******* pickActionForState ************")
        m = self.mean(state)
        v = self.variance(state)
        print("mean: " + str(m) + ", variance: " + str(v))
        action = numpy.random.normal(m, v)
        #Convert this into a value between 510 and 1023 encoder ticks
        #action = (1023.0 + 510.0) / 2 + action* 10
        print("action: " + str(action))

        pubMean = rospy.Publisher('horde_AContinuous/Mean', Float64, queue_size=10)
        pubMean.publish(m)

        pubVariance = rospy.Publisher('horde_AContinuous/Variance', Float64, queue_size=10)
        pubVariance.publish(v)

        pubAction = rospy.Publisher('horde_AContinuous/Action', Float64, queue_size=10)
        pubAction.publish(action)

        return action

    #This should probably not be defined with the actor critic, but rather be sent to the actor critic in the learn step
    def rewardOld(self, previousState, action, newState):
        if newState.encoder < 795:
            return 1
        else:
            return 0

    def reward(self, previousState, action, newState):
        pubReward = rospy.Publisher('horde_AC/reward', Float64, queue_size=10)

        #Higher reward, the closer you are to 550

        rewardGoingLeft = (1023.0 - newState.encoder) / 100.0
        rewardGoingRight = (newState.encoder - 510.0) / 100.0

        pubReward.publish(rewardGoingLeft)
        return rewardGoingLeft


    def learn(self, previousState, action, newState):
        print("============= In Continuous actor critic learn =========")

        reward = self.reward(previousState, action, newState)

        print("previous encoder: " + str(previousState.encoder) + ", speed: " + str(previousState.speed) + ", new encoder: " + str(newState.encoder) + " speed: " + str(newState.speed) +  ", action: " + str(action) + ", reward: " + str(reward))

        #Critic update
        tdError = reward - self.averageReward + numpy.inner(newState.X, self.valueWeights) - numpy.inner(previousState.X, self.valueWeights)
        print("tdError: " + str(tdError))
        self.averageReward = self.averageReward + self.rewardStep * tdError
        print("Average reward: " + str(self.averageReward))
        self.elibibilityTraceValue = self.lambdaValue * self.elibibilityTraceValue + previousState.X
        self.valueWeights = self.valueWeights + self.stepSizeValue * tdError * self.elibibilityTraceValue

        m = self.mean(previousState)
        v = self.variance(previousState)

        #Mean Update
        self.elibibilityTraceMean = self.lambdaPolicy * self.elibibilityTraceMean + ((action - m) * previousState.X)
        self.policyWeightsMean = self.policyWeightsMean + self.stepSizeMean * tdError * self.elibibilityTraceMean

        #Variance Update
        logPie = (numpy.power(action - m, 2) - numpy.power(v, 2)) * previousState.X
        self.elibibilityTraceVariance = self.lambdaPolicy * self.elibibilityTraceVariance + logPie
        self.policyWeightsVariance = self.policyWeightsVariance + self.stepSizeVariance * tdError * self.elibibilityTraceVariance

        if reward == 1:
            print("logPie: " + str(logPie))
            print("Elg trace variance: ")
            print(self.elibibilityTraceVariance)
            print("policyWeightsVariance: " )
            print(self.policyWeightsVariance)

        pubReward = rospy.Publisher('horde_AC/Reward', Float64, queue_size=10)
        pubReward.publish(self.reward)

        pubAvgReward = rospy.Publisher('horde_AC/avgReward', Float64, queue_size=10)
        pubAvgReward.publish(self.averageReward)
        print("============ End continuous actor critic learn ============")
        print("-")

