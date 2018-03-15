from threading import Thread
from time import sleep
import select
import socket
import socks
import ssl
import re

from adapt.intent import IntentBuilder
from mycroft.audio import wait_while_speaking
from mycroft import MycroftSkill, intent_handler
from mycroft.skills.core import MycroftSkill
from mycroft.util.log import getLogger
from mycroft.util import normalize

#########################################
# RFC					#
# https://tools.ietf.org/html/rfc1459	#
#########################################

LOGGER = getLogger(__name__)

class IRCSkill(MycroftSkill):
	def __init__(self):
		super(IRCSkill, self).__init__()
		# TODO make them configureable
		# TODO make them into lists
		# options
		self.settings['proxy'] = ""
		self.settings['proxy-port'] = 9050
		self.settings['proxy-user'] = ""
		self.settings['proxy-passwd'] = ""
		self.settings['server'] = "irc.flightgear.org"
		self.settings['server-password'] = ""
		self.settings['port'] = 6667
		self.settings['channel'] = "mycroft"
		self.settings['channel-password'] = ""
		self.settings['user'] = "dummy|m"
		self.settings['password'] = ""
		self.settings['ssl'] = False
		self.settings['debug'] = False

		# IPC for comunicating between threads
		self.irc_lock = False
		self.irc_cmd = ""
		self.irc_str = ""

	def initialize(self):
		if self.settings['proxy'] != "":
			if self.settings['debug']:
				self.speak("Using proxy: " + self.settings['proxy'])
				self.speak("Port: " + str(self.settings['proxy-port']))
			socks.set_default_proxy(socks.SOCKS5, self.settings['proxy'], self.settings['proxy-port'], True, 'user','passwd')
			socket.socket = socks.socksocket

		self._irc_start_thread()

	@intent_handler(IntentBuilder('ConnectIntent').require('connect'))
	def handle_connect_intent(self, message):
		# TODO ability to connect to different server
		if self.con_thread.isAlive() == False:
			self._irc_start_thread()
		if self.irc_lock == False:
			self.speak("Connecting")
			self.irc_lock == True
			self.irc_cmd = "connect"
			self.irc_str = ""
			self.irc_lock = False

	@intent_handler(IntentBuilder('JoinIntent').require('join'))
	def handle_join_intent(self, message):
		# TODO ability to join to different channels
		if self.con_thread.isAlive() == False:
			self._irc_start_thread()
		if self.irc_lock == False:
			self.speak("Joining")
			self.irc_lock == True
			self.irc_cmd = "join"
			self.irc_str = ""
			self.irc_lock = False

	@intent_handler(IntentBuilder('PartIntent').require('part'))
	def handle_part_intent(self, message):
		# TODO ability to join to different channels
		if self.con_thread.isAlive() == False:
			self._irc_start_thread()
		if self.irc_lock == False:
			self.speak("Parting")
			self.irc_lock == True
			self.irc_cmd = "part"
			self.irc_str = ""
			self.irc_lock = False

	@intent_handler(IntentBuilder('DisconnectIntent').require('disconnect'))
	def handle_disconnect_intent(self, message):
		# TODO ability to disconnect from different server
		if self.con_thread.isAlive() == False:
			self._irc_start_thread()
		if self.irc_lock == False:
			self.speak("Disconnecting")
			self.irc_lock == True
			self.irc_cmd = "disconnect"
			self.irc_str = ""
			self.irc_lock = False

	@intent_handler(IntentBuilder('SendIntent').require('send'))
	def handle_send_intent(self, message):
		# TODO ability to send to different users and channels
		if self.con_thread.isAlive() == False:
			self._irc_start_thread()
		if self.irc_lock == False:
			response = self.get_response("get_msg")
			if response != None:
				self.irc_lock == True
				self.irc_cmd = "send"
				self.irc_str = response
				self.irc_lock = False
			else:
				self.speak("I didn't understand a message")

	@intent_handler(IntentBuilder('DebugEnableIntent').require('debug-enable'))
	def handle_debug_enable_intent(self, message):
		self.settings['debug'] = True
		self.speak("Debugging enabled")

	@intent_handler(IntentBuilder('DebugDisableIntent').require('debug-disable'))
	def handle_debug_disable_intent(self, message):
		self.settings['debug'] = False
		self.speak("Debugging disabled")

	def _main_loop(self):
		connected = False
		joined = False
		while True:
			sleep(2)
			if connected:
				text = ""
				try:
					ready = select.select([irc], [], [], 2)
					if ready[0]:
						text = irc.recv(2040)
				except Exception:
					continue

				for line in text.splitlines():
					if line != "":
						if self.settings['debug']:
							self.speak(str(line))
							pass
		
						# Prevent Timeout
						match = re.search("^PING (.*)$", line, re.M)
						if match != None:
							irc.send('PONG ' + match.group(1) + '\r\n')
	
						match = re.search("^:(.*)!.*@.* QUIT", line, re.M)
						if match != None:
							self.speak(match.group(1) + " has disconnected")
	
						match = re.search("^:(.*)!.*@.* JOIN", line, re.M)
						if match != None:
							if match.group(1) != self.settings['user']:
								self.speak(match.group(1) + " has joined the channel")
	
						match = re.search("^:(.*)!.*@.* PART", line, re.M)
						if match != None:
							self.speak(match.group(1) + " has left the channel")
	
						match = re.search("^:(.*)!.*@.* QUIT", line, re.M)
						if match != None:
							self.speak(match.group(1) + " has disconnected")
	
						match = re.search("^:(.*)!.*@.* PRIVMSG #(.*) :(.*)", line, re.M)
						if match != None:
							self.speak(match.group(1) + " has written in " + match.group(2) + ": " + match.group(3))
	
						match = re.search("^:(.*)!.*@.* NOTICE #.* :(.*)", line, re.M)
						if match != None:
							self.speak(match.group(1) + " has written a notice to " + match.group(2) + ". The notice is: " + match.group(3))
	
						match = re.search("^:(.*)!.*@.* PRIVMSG " + re.escape(self.settings['user']) + " :(.*)$", line, re.M)
						if match != None:
							self.speak(line)
							self.speak(match.group(1) + " has written you a private message: " + match.group(2))

						match = re.search(":(.*)!.*@.* NOTICE " + re.escape(self.settings['user']) + " :(.*)", line)
						if match != None:
							self.speak(match.group(1) + " has written a private notice to you. The notice is: " + match.group(2))

			cmd = ""
			string = ""

			if self.irc_cmd != "":
				if self.irc_lock == False:
					self.irc_lock = True
					cmd = self.irc_cmd
					string = self.irc_str
					self.irc_cmd = ""
					self.irc_str = ""
					self.irc_lock = False

			if cmd != "":
				# check cmd and take action
				if cmd == "connect":
					# TODO add ability to connect to more than one server
					if connected == False:
						connected, irc = self._irc_connect(self.settings['server'], self.settings['port'], self.settings['ssl'], self.settings['server-password'], self.settings['user'], self.settings['password'])
					else:
						self.speak("Already connected")
	
				elif cmd == "join":
					if connected:
						joined = self._irc_join(irc, self.settings['channel'], self.settings['channel-password'])
					else:
						self.speak("Please connect to a server first")
	
				elif cmd == "part":
					if connected:
						if joined:
							joined = self._irc_part(irc, self.settings['channel'])
						else:
							self.speak("I'm in no channel I could part from")
					else:
						self.speak("Not connected to a server")
	
				elif cmd == "disconnect":
					if connected:
						connected = self._irc_disconnect(irc)
					else:
						self.speak("I'm to no server connected")
	
					if connected == False:
						joined = False
	
				elif cmd == "send":
					if connected:
						if joined:
							self._irc_send(irc, "#" + self.settings['channel'], string)
						else:
							self.speak("Please join a channel first")
					else:
						self.speak("Please connect to a server and join a channel first")

	def _irc_connect(self, server, port, ssl_req, server_password, user, password):
		irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #defines the socket

		# Connect
		try:
			if self.settings['debug']:
				self.speak("Server: " + server)
				self.speak("Port: " + str(port))
			irc.settimeout(15)
			irc.connect((server, port))
		except Exception as e:
			self.speak("Unable to connect to server.")
			if self.settings['debug']:
				self.speak("Error: " + str(e))
			return False, irc

		if ssl_req:
			if self.settings['debug']:
				self.speak("Use SSL")
			irc = ssl.wrap_socket(irc)

		irc.setblocking(0)
		if server_password != "":
			irc.send("PASS %s\n" % (password))
		irc.send("USER " + user + " " + user + " " + user + " :IRC via VOICE -> Mycroft\n")
		irc.send("NICK " + user + "\n")
		if password != "":
			irc.send("PRIVMSG nickserv :identify %s %s\r\n" % (user, password))

		self.speak("Connected")
		return True, irc

	def _irc_join(self, irc, channel, channel_password):
		# TODO add steps to be able to use a pw
		irc.send("JOIN #"+ channel +"\n")
		self.speak("Channel " + channel + " joined")
		return True

	def _irc_part(self, irc, channel):
		irc.send("PART #" + channel)
		self.speak("Parted")
		return False # this is the value that's written in `joined`

	def _irc_disconnect(self, irc):
		irc.send("QUIT :Disconnected my mycroft\n")
		irc.close()
		self.speak("Disconnected")
		return False # this is the value that's written in `connected`

	def _irc_send(self, irc, to, msg):
		irc.send("PRIVMSG " + to + " :" + msg + "\n")
		self.speak("Message sent")

	def _irc_start_thread(self):
		if self.settings['debug']:
			self.speak("Restart thread")
		self.con_thread = Thread(target=self._main_loop)
		self.con_thread.setDaemon(False)
		self.con_thread.start()

	def stop(self):
		pass

def create_skill():
	return IRCSkill()
"""
### Tail
tail_files = [
    '/tmp/file-to-tail.txt'
]


print "Establishing connection to [%s]" % (server)


tail_line = []
for i, tail in enumerate(tail_files):
    tail_line.append('')


while True:
    time.sleep(2)

    # Tail Files
    for i, tail in enumerate(tail_files):
        try:
            f = open(tail, 'r')
            line = f.readlines()[-1]
            f.close()
            if tail_line[i] != line:
                tail_line[i] = line
                irc.send("PRIVMSG %s :%s" % (channel, line))
        except Exception as e:
            print "Error with file %s" % (tail)
            print e

    try:
        text=irc.recv(2040)
        print text

        # Prevent Timeout
        if text.find('PING') != -1:
            irc.send('PONG ' + text.split() [1] + '\r\n')
    except Exception:
        continue
"""		
