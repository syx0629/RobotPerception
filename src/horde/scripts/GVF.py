import numpy
import rospy
from std_msgs.msg import Float64
from horde.msg import StateRepresentation

class GVF:
    def __init__(self, featureVectorLength, alpha, isOffPolicy, name = "GVF name"):
        #set up lambda, gamma, etc.
        self.name = name
        self.isOffPolicy = isOffPolicy
        self.numberOfFeatures = featureVectorLength
        self.lastState = 0
        self.lastObservation = 0
        self.weights = numpy.zeros(self.numberOfFeatures)
        self.hWeights = numpy.zeros(featureVectorLength)
        self.eligibilityTrace = numpy.zeros(self.numberOfFeatures)
        self.gammaLast = 1

        self.alpha = alpha
        self.lastAction = 0

    """
    gamma, cumulant, and policy functions can/should be overiden by the specific instantiation of the GVF based on the intended usage.
    """
    def gamma(self, state):
        return 0

    def cumulant(self, state):
        return 1

    def policy(self, state):
        #To be overwritten based on GVF's intended behavior if off policy. Otherwise 1 means on policy
        return 1

    def lam(self, state):
        return 0.95

    def rho(self, action, state):
        targetAction = self.policy(state)
        if (targetAction == action):
            return 1
        else:
            return 0

    def learn(self, lastState, action, newState):
        if self.isOffPolicy:
            self.gtdLearn(lastState, action, newState)
        else:
            self.tdLearn(lastState, action, newState)

    def gtdLearn(self, lastState, action, newState):

        print("")
        print("!!!!! LEARN  !!!!!!!")
        print("GVF name: " + str(self.name))
        print("For (" + str(lastState.encoder) +  ", " + str(lastState.speed) +  ") to (" + str(newState.encoder) + ", " + str(newState.speed) + ")")
        pred = self.prediction(lastState)
        print("--- Prediction for " + str(lastState.encoder) + ", " + str(lastState.speed) + " before learning: " + str(pred))
        print("alpha: " + str(self.alpha))
        #print("lastState: " )
        #print(lastState)
        print("action")
        print(action)
        #print("NewState")
        #print(newState)
        #print("New state rep:" + str(newState))
        #print("Weights before:")
        #print(self.weights)
        zNext = self.cumulant(newState)
        print("Cumulant: " + str(zNext))
        gammaNext = self.gamma(newState)
        print("gammaNext: " + str(gammaNext))
        lam = self.lam(newState)
        print("gammaLast: " + str(self.gammaLast))

        print("lambda: " + str(lam))
        #print("Eligibility before:")
        #print(self.eligibilityTrace)
        rho = self.rho(action, lastState)
        print("rho: " + str(rho))
        self.eligibilityTrace = rho * (self.gammaLast * lam * self.eligibilityTrace + lastState.X)
        #print("Eligibility trace after:")
        #print(self.eligibilityTrace)
        tdError = zNext + gammaNext * numpy.inner(newState.X, self.weights) - numpy.inner(lastState.X, self.weights)

        print("tdError: " + str(tdError))

        #print("hWeights before:")
        #print(self.hWeights)

        print("tdError: " + str(tdError))

        self.hWeights = self.hWeights + self.alpha * 0.1 * (tdError * self.eligibilityTrace - (numpy.inner(self.hWeights, lastState.X)) * lastState.X)

        #print("hWeights after:")
        #print(self.hWeights)

        #print("Weights before:")
        #print(self.weights)

        self.weights = self.weights + self.alpha * (tdError * self.eligibilityTrace - gammaNext * (1-lam)  * (numpy.inner(self.eligibilityTrace, self.hWeights) * newState.X))

        #print("wEights after: ")
        #print(self.weights)

        pred = self.prediction(lastState)
        print("Prediction for " + str(lastState.encoder) + ", " + str(lastState.speed)  + " after learning: " + str(pred))


        self.gammaLast = gammaNext

        if (lastState):
            pubPrediction = rospy.Publisher('horde_verifier/' + self.name + 'Prediction', Float64, queue_size=10)
            pubPrediction.publish(pred)
            #pubObs = rospy.Publisher('horde_verifier/NormalizedEncoderPosition', Float64, queue_size=10)
            #normalizedObs = 3.0 * (lastState.encoder - 510.0) / (1023.0-510.0)
            #pubObs.publish(normalizedObs )



    def tdLearn(self, lastState, action, newState):
        print("!!!!! LEARN  !!!!!!!")
        print("GVF name: " + str(self.name))
        print("For (" + str(lastState.encoder) +  ", " + str(lastState.speed) +  ") to (" + str(newState.encoder) + ", " + str(newState.speed) + ")")
        pred = self.prediction(lastState)
        print("--- Prediction for " + str(lastState.encoder) + ", " + str(lastState.speed) + " before learning: " + str(pred))

        print("alpha: " + str(self.alpha))
        #print("lastState: " )
        #print(lastState)
        print("action")
        print(action)
        #print("NewState")
        #print(newState)
        #print("New State:" + str(newState))
        #print("Weights before:")
        #print(self.weights)
        zNext = self.cumulant(newState)
        print("Cumulant: " + str(zNext))
        gammaNext = self.gamma(newState)
        print("gammaNext: " + str(gammaNext))
        lam = self.lam(newState)
        print("gammaLast: " + str(self.gammaLast))

        print("lambda: " + str(lam))
        #print("Eligibility before:")
        #print(self.eligibilityTrace)
        self.eligibilityTrace = self.gammaLast * lam * self.eligibilityTrace + lastState.X
        #print("Eligibility trace after:")
        #print(self.eligibilityTrace)

        tdError = zNext + gammaNext * numpy.inner(newState.X, self.weights) - numpy.inner(lastState.X, self.weights)

        print("tdError: " + str(tdError))
        #print("Weights before:")
        #print(self.weights)
        self.weights = self.weights + self.alpha * tdError * self.eligibilityTrace

        #print("wEights after: ")
        #print(self.weights)
        pred = self.prediction(lastState)
        print("Prediction for " + str(lastState.encoder) + ", " + str(lastState.speed)  + " after learning: " + str(pred))

        self.gammaLast = gammaNext

        if (lastState):
            pubPrediction = rospy.Publisher('horde_verifier/' + self.name + 'Prediction', Float64, queue_size=10)
            pubPrediction.publish(pred)

    def prediction(self, stateRepresentation):
        return numpy.inner(self.weights, stateRepresentation.X)