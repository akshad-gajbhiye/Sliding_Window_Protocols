# SimPy models for rdt_Sender and rdt_Receiver
# implementing the Selective Repeatative Protocol

# Author: Akshad Vivek Gajbhiye

import simpy
import random
import sys
from Packet import Packet



class rdt_Sender(object):
	
	def __init__(self,env):
		
		# Initialize variables and parameters
		self.env=env 
		self.channel=None
		
		# some default parameter values
		self.data_packet_length=10 # bits
		self.timeout_value=10 # default timeout value for the sender
		self.N=5 # Sender's Window size
		self.K=16 # Packet Sequence numbers can range from 0 to K-1

		# some state variables and parameters for the Go-Back-N Protocol
		self.base=1 # base of the current window 
		self.nextseqnum=1 # next sequence number
		self.sndpkt= {} # a buffer for storing the packets to be sent (implemented as a Python dictionary)
		self.timers= {} # a buffer for storing timers
		self.running= {}

		# some other variables to maintain sender-side statistics
		self.total_packets_sent=0
		self.num_retransmissions=0

		
		# timer-related variables
		self.timer_is_running=False
		self.timer=None

			
	
	def rdt_send(self,msg):
		# This function is called by the 
		# sending application.
			
		# check if the nextseqnum lies within the 
		# range of sequence numbers in the current window.
		# If it does, make a packet and send it,
		# else, refuse this data.

				
		if(self.nextseqnum in [(self.base+i)%self.K for i in range(0,self.N)]):
			print("TIME:",self.env.now,"RDT_SENDER: rdt_send() called for nextseqnum=",self.nextseqnum," within current window. Sending new packet.")
			# create a new packet and store a copy of it in the buffer
			self.sndpkt[self.nextseqnum]= Packet(seq_num=self.nextseqnum, payload=msg, packet_length=self.data_packet_length)
			# send the packet
			self.channel.udt_send(self.sndpkt[self.nextseqnum])
			self.total_packets_sent+=1
			
			# start the timer if required
			#if(self.base==self.nextseqnum):
			#	self.start_timer()
			self.start_timer(self.nextseqnum)
			#self.timers[self.nextseqnum]=1
			print(self.timers)
			# update the nextseqnum
			self.nextseqnum = (self.nextseqnum+1)%self.K
			return True
		else:
			print("TIME:",self.env.now,"RDT_SENDER: rdt_send() called for nextseqnum=",self.nextseqnum," outside the current window. Refusing data.")
			return False
		
	
	def rdt_rcv(self,packt):
		# This function is called by the lower-layer 
		# when an ACK packet arrives
		
		if (packt.corrupted==False):
			print("TIME:",self.env.now,"RDT_SENDER: Got ACK",packt.seq_num)
			print(self.timers)
			# check if we got an ACK for a packet within the current window.
			if packt.seq_num in self.sndpkt.keys():
				if packt.seq_num == self.base:
                    # stop the timer for the packet at base
					self.stop_timer(packt.seq_num)
                    # slide the window
					self.base = (self.base + 1) % self.K
					del self.sndpkt[packt.seq_num]
					del self.timers[packt.seq_num]
					print("after delete:", self.timers)

                    # # start timer for the new base packet
					# if (self.base + self.N - 1) % self.K in self.sndpkt:
					# 	self.start_timer((self.base + self.N - 1) % self.K)
					#if (packt.seq_num == self.base):
				    #while(self.base in self.timers):
					while (self.base in self.timers):
						if (self.running[self.base]==False):
							del self.sndpkt[self.base]
							del self.timers[self.base]
							self.base = (self.base + 1) % self.K
						else:
							break
				else:
					self.stop_timer(packt.seq_num)
					
				print("TIME:", self.env.now, "RDT_SENDER: Got an ACK", packt.seq_num,". Updated window:", [(self.base + i) % self.K for i in range(0, self.N)], "base =", self.base,"nextseqnum =", self.nextseqnum)
			else:
				print("TIME:", self.env.now, "RDT_SENDER: Got an ACK", packt.seq_num, " for a packet not in the buffer. Ignoring it.")
	
    # Finally, these functions are used for modeling a Timer's behavior.
	def timer_behavior(self,seq_num):
		try:
			# Wait for timeout 
			self.timer_is_running=True
			self.running[seq_num]=True
			yield self.env.timeout(self.timeout_value)
			self.timer_is_running=False
			self.running[seq_num]=False
			# take some actions 
			self.timeout_action(seq_num)
		except simpy.Interrupt:
			# stop the timer
			self.timer_is_running=False
			self.running[seq_num]=False

	# This function can be called to start the timer
	def start_timer(self,seq_num):
		#assert(self.timer_is_running==False
		assert ((seq_num in self.timers.keys())==False)
		self.timers[seq_num]=self.env.process(self.timer_behavior(seq_num))
		#print("after starting",self.timers.keys())
		print("TIME:",self.env.now,"TIMER STARTED for a timeout of ",self.timeout_value, "for Packet", seq_num)

	# This function can be called to stop the timer
	def stop_timer(self,seq_num):
		#assert(self.timer_is_running==True)
		assert ((seq_num in self.timers.keys())==True)
		#del self.timers[seq_num]
		#print("after stop", self.timers.keys())
		self.timers[seq_num].interrupt()
		print("TIME:",self.env.now,"TIMER STOPPED for Packet", seq_num)
	
	def restart_timer(self,seq_num):
		# stop and start the timer
		assert((seq_num in self.timers.keys())==True)
		#self.timers[seq_num].interrupt()
		#del self.timers[seq_num]
		#assert(self.timer_is_running==False)
		self.stop_timer(seq_num)
		self.timer=self.env.process(self.timer_behavior(seq_num))
		self.timers[seq_num]=self.env.process(self.timer_behavior(seq_num))
		print("TIME:",self.env.now,"TIMER RESTARTED for a timeout of ",self.timeout_value, "for Packet", seq_num)


	# Actions to be performed upon timeout
	def timeout_action(self, seq_num):
		
		# re-send the packet for which an ACK has been pending
		print("TIME:",self.env.now,"RDT_SENDER: TIMEOUT OCCURED. Re-transmitting packet: ",seq_num)
		self.channel.udt_send(self.sndpkt[seq_num])
		self.num_retransmissions+=1
		self.total_packets_sent+=1
		# Re-start the timer
		#self.timers[seq_num].interrupt()
		#self.stop_timer(seq_num)
		del self.timers[seq_num]
		self.start_timer(seq_num)
		
	# A function to print the current window position for the sender.
	def print_status(self):
		print("TIME:",self.env.now,"Current Sender window:", [(self.base+i)%self.K for i in range(0,self.N)],"base =",self.base,"nextseqnum =",self.nextseqnum)
		print("---------------------")


#==========================================================================================

class rdt_Receiver(object):
	
	def __init__(self,env):
		
		# Initialize variables
		self.env=env 
		self.receiving_app=None
		self.channel=None

		# some default parameter values
		self.ack_packet_length=10 # bits
		self.N=6 # range of sequence numbers expected
		self.K=10 # Packet Sequence numbers can range from 0 to K-1

		# some state variables and parameters for the Go-Back-N Protocol
		self.base=1 # base of the current window 
		self.nextseqnum=1 # next sequence number
		self.pkts= {} # a buffer for storing the packets to be sent (implemented as a Python dictionary)

		#initialize state variables
		self.sndpkt= Packet(seq_num=0, payload="ACK",packet_length=self.ack_packet_length)
		self.total_packets_sent=0
		self.num_retransmissions=0

		

	def rdt_rcv(self,packt):
		# This function is called by the lower-layer 
		# when a packet arrives at the receiver
		if(packt.corrupted==False):
			print("TIME:",self.env.now,"RDT_RECEIVER: Got packet",packt.seq_num,". Sent ACK")
			self.sndpkt= Packet(seq_num=packt.seq_num, payload="ACK",packet_length=self.ack_packet_length) 
			self.channel.udt_send(self.sndpkt)
			self.total_packets_sent+=1

		if(packt.corrupted==False and packt.seq_num in [(self.base+i)%self.K for i in range(0,self.N)]):
			self.pkts[packt.seq_num] = packt			
			# extract and deliver data
			print("Packets stored: ", self.pkts)
			if (packt.seq_num == self.base):
				while(self.base in self.pkts):
					self.receiving_app.deliver_data(self.pkts[self.base].payload)
					print("TIME:",self.env.now,"RDT_RECEIVER: Delivered data:",packt.seq_num,". to RECEIVING APPLICATION")
					del self.pkts[self.base]
					self.base = (self.base + 1) % self.K
				print("TIME:",self.env.now,"Current Receiver window:", [(self.base+i)%self.K for i in range(0,self.N)],"base =",self.base,"nextseqnum =",self.nextseqnum)
		
		else:
			print("TIME:",self.env.now,"RDT_RECEIVER: got corrupted packet")