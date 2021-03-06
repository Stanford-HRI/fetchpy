import math
import logging
import numpy
import openravepy
import warnings
from prpy.base.manipulator import Manipulator

logger = logging.getLogger('arm')

class ARM(Manipulator):
	def  __init__(self, sim, namespace='',
		iktype = openravepy.IkParameterization.Type.Transform6D):
		Manipulator.__init__(self)
		self.simulated = sim
		self._iktype = iktype
		self.namespace = namespace

		if iktype is not None:
			self._SetupIK(iktype)
		if sim:
			from prpy.simulation import ServoSimulator
			self.servo_simulator = ServoSimulator(self, rate = 20, watchdog_timeout = 0.1)

	def IsSimulated(self):
		""" Decides if manipulator is simulated.
		@returns bool
		"""
		return self.simulated

	def GetJointNames(self):
		""" sets the joint names based between arm or arm_torso
		@returns list of joint names
		"""
		jointnames = ['shoulder_pan_joint',
		 'shoulder_lift_joint',
		 'upperarm_roll_joint',
		 'elbow_flex_joint',
		 'forearm_roll_joint',
		 'wrist_flex_joint',
		 'wrist_roll_joint']
		if self.namespace == 'arm_torso':
			jointnames.insert(0,'torso_lift_joint')

		return jointnames

	def CloneBindings(self, parent):
		Manipulator.CloneBindings(self, parent)
		self.simulated = True
		self._iktype = parent._iktype
		if self._iktype is not None:
			self._SetupIK(self._iktype)

	def _SetupIK(self, iktype):
		""" creates Ikfast file for chosen manipulator
		"""
		from openravepy.databases.inversekinematics import InverseKinematicsModel

		robot = self.GetRobot()
		self.ikmodel = InverseKinematicsModel(robot=robot, manip=self,iktype=iktype)
		if not self.ikmodel.load():
			if(self.namespace == 'arm'):
				self.ikmodel.generate(iktype=iktype, precision=4,
					freeindices=[self.GetIndices()[2]])
				self.ikmodel.save()
			else:
				self.ikmodel.generate(iktype=iktype, precision=4,
					freeindices=[self.GetIndices()[4],self.GetIndices()[3]])
				self.ikmodel.save()


	def SetStiffnes(self,stiffness):
		""" sets stiffness of the manipulator
		"""
		raise NotImplementedError('Not Implemented yet.'
    		'There is a gravity compensation controller on real robot. Just subscribe to that and enable/disable')


	def SetTrajectoryExecutionOptions(self, traj, stop_on_stall=False,
		stop_on_ft=False, force_magnitude=None, force_direction=None,torque=None):
		"""Set OWD's trajectory execution options on trajectory.
	        @param stop_on_stall aborts the trajectory if the arm stalls
	        @param stop_on_ft aborts the trajectory if the force/torque
	                          sensor reports a force or torque that exceeds
	                          threshold specified by the force_magnitude,
	                          force_direction, and torque options
	        @param force_magnitude force threshold value, in Newtons
	        @param force_direction unit vector in the force/torque coordinate
	                               frame, which is int he same orientation as the
	                               hand frame.
	        @param torque vector of the three torques
	        """
	        raise NotImplementedError('ooh. We can do it manually. Lets implement this')

	def Servo(self, velocities):
		"""Servo with a vector of instantaneous joint velocities.
		@param velocities joint velocities, in radians per second
		"""
		num_dof = len(self.GetArmIndices())
		if len(velocities) !=num_dof:
			raise ValueError('Incorrect number of joint velocities. '
                             'Expected {0:d}; got {0:d}.'.format(
                             num_dof, len(velocities)))
		if not self.simulated:
			raise NotImplementedError('Servoing and velocity control not yet'
                                      'supported under ros_control.')
		else:
			self.servo_simulator.SetVelocity(velocities)

	def servoTo(self, target, duration, timeStep = 0.05,collisionChecking = True):
		"""Servo the arm towards a target configuration over some duration.
		Servos the arm towards a target configuration with a constant joint
		velocity. This function uses the \ref Servo command to control the arm
		and must be called repeatidly until the arm reaches the goal. If \tt
		collisionChecking is enabled, then the servo will terminate and return
		False if a collision is detected with the simulation environment.
		@param target desired configuration
		@param duration duration in seconds
		@param timestep period of the control loop, in seconds
		@param collisionchecking check collisions in the simulation environment
		@return whether the servo was successful
		"""
		steps = int(math.ceil(duration/timeStep))
		original_dofs = self.GetRobot().GetDOFValues(self.GetArmIndices())
		velocity = numpy.array(target - self.GetRobot().GetDOFValues(self.GetArmIndices()))
		velocities = [v/steps for v in velocity]
		inCollision = False
		if collisionChecking:
			inCollision = self.CollisionCheck(target)
		if not inCollision:
			for i in range(1, steps):
				import time
				self.Servo(velocities)
				time.sleep(timeStep)
			self.Servo([0]* len(self.GetArmIndices()))
			return True
		else:
			return False


	def GetVelocityLimits(self, openrave=None):
		logger.warning('Only getting velocity limits of OR model, The function should'
    		'print an warning if the or velocity and real robot velocity does not match')
		return Manipulator.GetVelocityLimits(self)

	def SetVelocityLimits(self, velocity_limits, min_accel_time,openrave=True):
		logger.warning('Only setting velocity limits of OR model, The function should'
    		'set the velocity limit of both OR and real robot')
		Manipulator.SetVelocityLimits(self, velocity_limits, min_accel_time)

	def GetTrajectoryStatus(manipulator):
		"""Gets the status of the current (or previous) trajectory executed by OWD.
		@return status of the current (or previous) trajectory executed
		"""
		raise NotImplementedError('GetTrajectoryStatus not supported on manipulator.'
			' Use returned TrajectoryFuture instead.')

	def ClearTrajectoryStatus(manipulator):
		"""Clears the current trajectory execution status.
		 This resets the output of \ref GetTrajectoryStatus.
		"""
		raise NotImplementedError('ClearTrajectoryStatus not supported on manipulator.')

	def MoveUntilTouch(manipulator, direction, distance, max_distance=None,
		max_force=5.0, max_torque=None, ignore_collisions=None,velocity_limit_scale=0.25, **kw_args):
		"""Execute a straight move-until-touch action.
		This action stops when a sufficient force is is felt or the manipulator
		moves the maximum distance. The motion is considered successful if the
		end-effector moves at least distance. In simulation, a move-until-touch
		action proceeds until the end-effector collids with the environment.

		@param direction unit vector for the direction of motion in the world frame
		@param distance minimum distance in meters
		@param max_distance maximum distance in meters
		@param max_force maximum force in Newtons
		@param max_torque maximum torque in Newton-Meters
		@param ignore_collisions collisions with these objects are ignored when
		planning the path, e.g. the object you think you will touch
		@param velocity_limit_scale A multiplier to use to scale velocity limits
		when executing MoveUntilTouch ( < 1 in most cases).
		@param **kw_args planner parameters
		@return felt_force flag indicating whether we felt a force.
		"""

		from contextlib import nested
		from openravepy import CollisionReport, KinBody, Robot, RaveCreateTrajectory
		from prpy.planning.exceptions import CollisionPlanningError

		delta_t = 0.01
		robot = manipulator.GetRobot()
		env = robot.GetEnv()
		dof_indices = manipulator.GetArmIndices()

		direction = numpy.array(direction, dtype='float')

		# Default argument values.
		if max_distance is None:
			max_distance = 1.
			warnings.warn('MoveUntilTouch now requires the "max_distance" argument.'
			' This will be an error in the future.',DeprecationWarning)

		if max_torque is None:
			max_torque = numpy.array([100.0, 100.0, 100.0])

		if ignore_collisions is None:
			ignore_collisions = []

		with env:
			# Compute the expected force direction in the hand frame.
			hand_pose = manipulator.GetEndEffectorTransform()
			force_direction = numpy.dot(hand_pose[0:3, 0:3].T, -direction)

			# Disable the KinBodies listed in ignore_collisions. We backup the
			# "enabled" state of all KinBodies so we can restore them later.
			body_savers = [body.CreateKinBodyStateSaver() for body in ignore_collisions]
			robot_saver = robot.CreateRobotStateSaver(Robot.SaveParameters.ActiveDOF
				| Robot.SaveParameters.ActiveManipulator
				| Robot.SaveParameters.LinkTransformation)

			with robot_saver, nested(*body_savers) as f:
				manipulator.SetActive()
				robot_cspec = robot.GetActiveConfigurationSpecification()

				for body in ignore_collisions:
					body.Enable(False)

				path = robot.PlanToEndEffectorOffset(direction=direction,
					distance=distance, max_distance=max_distance, **kw_args)

		# Execute on the real robot by tagging the trajectory with options that
		# tell the controller to stop on force/torque input.
		if not manipulator.simulated:
			raise NotImplementedError('MoveUntilTouch not yet implemented under ros_control.')

		# Forward-simulate the motion until it hits an object.
		else:
			traj = robot.PostProcessPath(path)
			is_collision = False

			traj_cspec = traj.GetConfigurationSpecification()
			new_traj = RaveCreateTrajectory(env, '')
			new_traj.Init(traj_cspec)

			robot_saver = robot.CreateRobotStateSaver(Robot.SaveParameters.LinkTransformation)

			with env, robot_saver:
				for t in numpy.arange(0, traj.GetDuration(), delta_t):
					waypoint = traj.Sample(t)

					dof_values = robot_cspec.ExtractJointValues(
					waypoint, robot, dof_indices, 0)
					manipulator.SetDOFValues(dof_values)

					# Terminate if we detect collision with the environment.
					report = CollisionReport()
					if env.CheckCollision(robot, report=report):
						logger.info('Terminated from collision: %s',
							str(CollisionPlanningError.FromReport(report)))
						is_collision = True
						break
					elif robot.CheckSelfCollision(report=report):
						logger.info('Terminated from self-collision: %s',
							str(CollisionPlanningError.FromReport(report)))
						is_collision = True
						break

					#Build the output trajectory that stops in contact.
					if new_traj.GetNumWaypoints() == 0:
						traj_cspec.InsertDeltaTime(waypoint, 0.)
					else:
						traj_cspec.InsertDeltaTime(waypoint, delta_t)

					new_traj.Insert(new_traj.GetNumWaypoints(), waypoint)

			if new_traj.GetNumWaypoints() > 0:
				robot.ExecuteTrajectory(new_traj)

			return is_collision
