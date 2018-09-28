#coding=utf-8
#!/usr/bin/env python3
#
#    This file is part of Zen python
#    Copyright (C) 2017 Zen python
#
#    Zen python is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Zen python is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Zen python.  If not, see <http://www.gnu.org/licenses/>.


from ctypes import *
import sys, time, getopt
import numpy as np
import threading
import json
from geventwebsocket import WebSocketError

class ZEN(object):
    def __init__(self, dll, boardsize, komi, strength, threads, resign, thinkinterval, printinterval):
        self.name = 'Zen7'
        self.version = '0.4'
        #self.name = 'Leela Zero'
        #self.version = '0.16'

        self.Threads = threads
        self.Strength = strength#count, 45000 means 1500*30s, very powerful machine think 30s

        self.ZenDLL = dll
        self.Komi = komi
        self.BoardSize = boardsize
        self.Handicap = 0

        self.Sgf = []
        self.PlayerBlack, self.PlayerWhite, self.ResultStr='','',''
        #self.move=[] #playlist[]
        self.playlist=[]
        #self.movestr=[] #str
        self.gameinfo=[] #suitable to dict data type
        # unknown: CA FF-4 RU TC TT C AP GM-1 GN DT BR WR TM
        # known: SZ PB PW KM HA RE
        self.gamelen=0
        self.passcount=0
        self.blackcount=0
        self.whitecount=0
        self.blackpass=0
        self.whitepass=0

        self.MaxSimulations = 1000000000#MaxSimulations = 1000000000 zliu: it's MCTS Playout, only 29 MCTS will be 1 NN eval
        self.MaxTime = 1000000000.0#MaxTime = c_float(1000000000.0), Time*Games/s=Playout
        self.PnLevel = 3
        self.PnWeight = c_float(1.0)
        self.VnMixRate = c_float(0.75)
        self.ResignRate=resign

        self.ThinkInterval=thinkinterval
        self.PrintInterval=printinterval
        
        self.analyzeStatus = 0

        self.SabakiFlat = 1 #0:off 1:on

        #statistics
        #countarray=[]
        self.Itemall = []

        self.X, self.Y, self.P, self.W, self.S = c_int(0), c_int(0), c_int(0), c_float(0), create_string_buffer(100)

        Print('')
        Print('Starting Zen7...')
        try:
            Zen = CDLL(self.ZenDLL)
        except WindowsError:
            Help()
        Print(self.ZenDLL + ' load ok')

        ### Zen7's address, 36 total
        self.ZenAddStone = Zen[1] #bool ZenAddStone(int,int,int)
        self.ZenIsInitialized = Zen[14] #bool ZenIsInitialized(void)
        self.ZenIsLegal = Zen[15] #bool ZenIsLegal(int,int,int)
        self.ZenIsSuicide = Zen[16] #bool ZenIsSuicide(int,int,int)
        self.ZenIsThinking = Zen[17] #bool ZenIsThinking(void)
        self.ZenPlay = Zen[20] #bool ZenPlay(int,int,int)
        self.ZenUndo = Zen[35] #bool ZenUndo(int)
        self.ZenGetBestMoveRate = Zen[4] #int ZenGetBestMoveRate(void)
        self.ZenGetBoardColor = Zen[5] #int ZenGetBoardColor(int,int)
        self.ZenGetHistorySize = Zen[6] #int ZenGetHistorySize(void)
        self.ZenGetNextColor = Zen[7] #int ZenGetNextColor(void)
        self.ZenGetNumBlackPrisoners = Zen[8] #int ZenGetNumBlackPrisoners(void)
        self.ZenGetNumWhitePrisoners = Zen[9] #int ZenGetNumWhitePrisoners(void)
        self.ZenClearBoard = Zen[2] #void ZenClearBoard(void)
        self.ZenFixedHandicap = Zen[3] #void ZenFixedHandicap(int)
        self.ZenGetTopMoveInfo = Zen[12] #void ZenGetTopMoveInfo(int,int &,int &,int &,float &,char *,int)
        self.ZenInitialize = Zen[13] #void ZenInitialize(char const *)
        self.ZenMakeShapeName = Zen[18] #void ZenMakeShapeName(int,int,int,char *,int)
        self.ZenPass = Zen[19] #void ZenPass(int)
        self.ZenReadGeneratedMove = Zen[21] #void ZenReadGeneratedMove(int &,int &,bool &,bool &)
        self.ZenSetBoardSize = Zen[22] #void ZenSetBoardSize(int)
        self.ZenSetKomi = Zen[23] #void ZenSetKomi(float)
        self.ZenSetMaxTime = Zen[24] #void ZenSetMaxTime(float)
        self.ZenSetNextColor = Zen[25] #void ZenSetNextColor(int)
        self.ZenSetNumberOfSimulations = Zen[26] #void ZenSetNumberOfSimulations(int)
        self.ZenSetNumberOfThreads = Zen[27] #void ZenSetNumberOfThreads(int)
        self.ZenSetPnLevel = Zen[28] #void ZenSetPnLevel(int)
        self.ZenSetPnWeight = Zen[29] #void ZenSetPnWeight(float)
        self.ZenSetVnMixRate = Zen[30] #void ZenSetVnMixRate(float)
        self.ZenStartThinking = Zen[31] #void ZenStartThinking(int)
        self.ZenStopThinking = Zen[32] #void ZenStopThinking(void)
        self.ZenTimeLeft = Zen[33] #void ZenTimeLeft(int,int,int)
        self.ZenTimeSettings = Zen[34] #void ZenTimeSettings(int,int,int)
        
        self.Zen_10 = Zen[10] #void ZenGetPolicyKnowledge(int (* const)[19])
        self.Zen_11 = Zen[11] #void ZenGetTerritoryStatictics(int (* const)[19])

        self.ZenInitialize('')
        self.ZenSetNumberOfThreads(self.Threads)
        self.ZenSetNumberOfSimulations(self.MaxSimulations)
        self.ZenSetMaxTime(c_float(self.MaxTime))
        self.ZenSetBoardSize(self.BoardSize)
        self.ZenSetKomi(c_float(self.Komi))

        Print('Zen Initialize ok(%d)' % self.ZenIsInitialized())
        Print('Threads: %d' % self.Threads)
        Print('MaxSimulations: %d (playouts, MCTS search)' % self.MaxSimulations)
        Print('MaxTime: %.1f' % self.MaxTime)
        Print('ResignRate: %.2f' % self.ResignRate)

        Print('Strength: %d (counts, NN eval)' % self.Strength)
        Print('BoardSize: %d' % self.BoardSize)
        Print('Komi: %.1f' % self.Komi)
        Print('')

        self.ZenSetPnLevel(3)
        self.ZenSetPnWeight(c_float(1.0))
        self.ZenSetVnMixRate(c_float(0.75))

        self.ZenClearBoard()

    def clear(self):
        self.ZenClearBoard()
        self.Sgf = []
        self.Itemall = []
        self.playlist = []
        self.gamelen=0
        self.passcount=0
        self.blackcount=0
        self.whitecount=0
        self.blackpass=0
        self.whitepass=0

    def ZenGetPolicyKnowledge(self):
        k = ((c_int * 19) * 19)()
        #Zen[10](k)
        self.Zen_10(k)
        return k

    def print19(self,t):
        for i in range(0, self.BoardSize):
            l=[]
            for j in range(0, self.BoardSize):
                #l.append( '%5d' % t[i][j] )
                l.append( '%d' % t[i][j] )
            print(' '.join(l))

    def ZenGetTerritoryStatictics(self):
        t = ((c_int * 19) * 19)()
        #Zen[11](t)
        self.Zen_11(t)
        return t

    def PrintTop(len):
        for N in range(0, len):
            X, Y, P, W, S = c_int(0), c_int(0), c_int(0), c_float(0), create_string_buffer(100)
            ret = ZenGetTopMoveInfo(N, byref(X), byref(Y), byref(P), byref(W), S, 99)
            Print('ret: %d %d,%d %d %.2f %s' % (ret,X.value,Y.value,P.value,W.value,S.value))

    def showboard(self):
      Print("")
      Print("Black Passes: %3d    White Passes: %3d" % (self.blackpass, self.whitepass ))
      Print("Passes: %d            Black (X) Prisoners: %d" % (self.passcount,self.ZenGetNumBlackPrisoners() ))
      Print("%s to move    White (O) Prisoners: %d" % ("Black (X)" if self.ZenGetNextColor()==2 else "White (O)",self.ZenGetNumWhitePrisoners()))
      Print("")
      gamelen=len(self.playlist)
      #print(self.playlist)
      Print('Game len: %d' % gamelen)
      Print("   a b c d e f g h j k l m n o p q r s t")
      for i in range(0, self.BoardSize):
        line = "%2d" % (self.BoardSize-int(i))
        last=0
        for j in range(0, self.BoardSize):
          if (gamelen>0) and ((j==self.playlist[gamelen-1][0]) and (i==self.playlist[gamelen-1][1])):
            line += "(%s)" % ("." if self.ZenGetBoardColor(j,i) == 0 else "X" if self.ZenGetBoardColor(j,i) == 2 else "O")
            #line += " %s " % ("." if self.ZenGetBoardColor(j,i) == 0 else "X" if self.ZenGetBoardColor(j,i) == 2 else "O")
            last=1
          else:
            if last==0:
              line += " %s" % ("." if self.ZenGetBoardColor(j,i) == 0 else "X" if self.ZenGetBoardColor(j,i) == 2 else "O")
            else:
              last=0
              line += "%s" % ("." if self.ZenGetBoardColor(j,i) == 0 else "X" if self.ZenGetBoardColor(j,i) == 2 else "O")
        line += " %2d" % (self.BoardSize-int(i))
        Print(line)
      Print("   a b c d e f g h j k l m n o p q r s t")
      Print("")
      Print("Black time: ??:??:??")
      Print("White time: ??:??:??")
      Print("")

    def PrintOneTopMoveDebug(item):
        Print('%d,%d %d %.2f %s' % (item[0],item[1],item[2],item[3]*100,item[4]))

    def PrintTopMoveDebug(list):
        listlen=len(list)
        #if listlen>1: listlen=1
        for i in range(0, listlen):
          PrintOneTopMoveDebug(list[i])

    def PrintListDebug(list, list_prv):
        Print('')
        Print('list:')
        PrintTopMoveDebug(list)
        Print('list previous:')
        PrintTopMoveDebug(list_prv)

    def PrintOneTopMove(self, item,C):
        #Print('%s %s[%s] -> %8d [%s],%s%% [%s], %s' % (('W' if C== 1 else 'B'), item[4].split()[0].ljust(4), \
        #    item[5], item[2], item[6], ('%.2f' % (item[3] * 100)).rjust(6), item[7], item[4]))
        Print('%s %s -> %8d,%s%%, %s' % (('W' if C== 1 else 'B'), item[4].split()[0].ljust(4), \
            item[2], ('%.2f' % (item[3] * 100)).rjust(6), item[4]))

    def PrintTopMove(self, list,C):
        listlen=len(list)
        for i in range(0, listlen):
            self.PrintOneTopMove(list[i],C)

    def PrintAnalyze(list):
        listlen=len(list)
        for i in range(0, listlen):
            item = list[i]
            #info move P1 visits 3 winrate 5337 order 0 pv P1 J17
            #Print('info color %s move %s visits %d winrate %d order %d pv %s' % (('W' if C== 1 else 'B'), item[4].split()[0], item[2], item[3] * 10000, i, item[4]))
            Print('info move %s visits %d winrate %d order %d pv %s' % (item[4].split()[0], item[2], item[3] * 10000, i, item[4]))

    def GetTopMoveList(self, num):
        #global X, Y, P, W, S
        itemlist=[]
        for i in range(0, num):
          ret = self.ZenGetTopMoveInfo(i, byref(self.X), byref(self.Y), byref(self.P), byref(self.W), self.S, 99)
          #Print('ret: %d %d %.2f %s' % (ret,P.value,W.value,S.value))
          if self.P.value == 0:
            return itemlist
            break
          Item = [self.X.value, self.Y.value, self.P.value, self.W.value, self.S.value, '+', '+', '+']
          itemlist.append([self.X.value, self.Y.value, self.P.value, self.W.value, self.S.value, '+', '+', '+'])
        return itemlist

    def ZenGenMove(self, C):
        #global blackcount, whitecount
        #global X, Y, P, W, S
        list,list_prv,list_tmp=[],[],[]
        thinkcount=0

        self.ZenStartThinking(C)

        reason = 'Stop by Zen'
        while self.ZenIsThinking() != -0x80000000:
            thinkcount+=1
            #PrintListDebug(list, list_prv)
            time.sleep(self.ThinkInterval)
            list_tmp=self.GetTopMoveList(5)
            if len(list_tmp)==0:
                #Print('P.value==0')
                continue
            elif list_tmp[0][2]>=self.Strength:
                self.ZenStopThinking()
                list_tmp=self.GetTopMoveList(5)
                #Print('P.value>=Strength')
                reason = 'Stop by %d >= %d' % ( list_tmp[0][2], self.Strength )
                list_prv=list
                list=list_tmp
                break
            else:
                if ((self.ThinkInterval*thinkcount)%self.PrintInterval)==0:
                    Print('')
                    self.PrintTopMove(list_tmp,C)
                list_prv=list
                list=list_tmp
            #time.sleep(ThinkInterval)

        self.ZenStopThinking()#zliu: maybe useless
        #PrintListDebug(list, list_prv)
        self.Itemall.append([C, list, list_prv])
        if len(list)==0:
            Print('%s-%s %s No. %3d %.1fs %s %d %.2f%% %s' % (self.name, self.version, 'B' if C==2 else 'W', self.blackcount+self.whitecount, thinkcount*self.ThinkInterval, 'pass', 0, 0, reason) )
            if C==2 : self.blackpass+=1
            else:     self.whitepass+=1
            return list
        else:
            Print('%s-%s %s No. %3d %.1fs %s %d %.2f%% %s' % (self.name, self.version, 'B' if C==2 else 'W', self.blackcount+self.whitecount, thinkcount*self.ThinkInterval, list[0][4].split()[0], list[0][2], list[0][3]*100, reason) )
        
        if C==2 : self.blackcount+=1
        else:     self.whitecount+=1
        self.PrintTopMove(list,C)
        return list

        #Print('   Prisoners: Black %d, White %d %s-%s %d %.2f%%' % (ZenGetNumBlackPrisoners(), ZenGetNumWhitePrisoners(), name, version, P.value, W.value*100) )

    def final_score_V1(self):
      str=''
      bt,wt=[0]*10,[0]*10
      t=self.ZenGetTerritoryStatictics()
      for i in range(0, self.BoardSize):
        for j in range(0, self.BoardSize):
          if t[i][j] > 900: bt[9]+=1
          if t[i][j] > 800: bt[8]+=1
          if t[i][j] > 700: bt[7]+=1
          if t[i][j] > 600: bt[6]+=1
          if t[i][j] > 500: bt[5]+=1
          if t[i][j] > 400: bt[4]+=1
          if t[i][j] > 300: bt[3]+=1
          if t[i][j] > 200: bt[2]+=1
          if t[i][j] > 100: bt[1]+=1
          if t[i][j] > 0: bt[0]+=1

          if t[i][j] < -900: wt[9]+=1
          if t[i][j] < -800: wt[8]+=1
          if t[i][j] < -700: wt[7]+=1
          if t[i][j] < -600: wt[6]+=1
          if t[i][j] < -500: wt[5]+=1
          if t[i][j] < -400: wt[4]+=1
          if t[i][j] < -300: wt[3]+=1
          if t[i][j] < -200: wt[2]+=1
          if t[i][j] < -100: wt[1]+=1
          if t[i][j] < 0: wt[0]+=1
      Print('Total: %d Komi: %.1f' % (self.gamelen, self.Komi))
      for j in range(0,9):
        i=9-j
        Print('%3d Black: %d White: %d Result: %.1f' % (i*100, bt[i],wt[i],bt[i]-wt[i]-self.Komi))
      rt9=bt[9]-wt[9]-self.Komi
      if rt9>0 : str='B+%.1f' % rt9
      else: str='W+%.1f' % -rt9
      return str

    def final_score(self):
        r,s=self.ZenScore()
        return s

    def stat_territory(self, threshhold, t):
      black_alive, black_capture, black_territory=0,0,0
      white_alive, white_capture, white_territory=0,0,0

      # recalculate territory according to around threshhold
      t_b = ((c_int * 19) * 19)()
      t_w = ((c_int * 19) * 19)()
      for i in range(0, self.BoardSize):
        for j in range(0, self.BoardSize):
            t_b[i][j] = -1
            t_w[i][j] = -1
            if (i-1)<0 or t[i-1][j]>threshhold:
                if (i+1)==self.BoardSize or t[i+1][j]>threshhold:
                    if (j-1)<0 or t[i][j-1]>threshhold:
                        if (j+1)==self.BoardSize or t[i][j+1]>threshhold:
                            t_b[i][j] = 2
            if (i-1)<0 or t[i-1][j]<-threshhold:
                if (i+1)==self.BoardSize or t[i+1][j]<-threshhold:
                    if (j-1)<0 or t[i][j-1]<-threshhold:
                        if (j+1)==self.BoardSize or t[i][j+1]<-threshhold:
                            t_w[i][j] = 1

      for i in range(0, self.BoardSize):
        for j in range(0, self.BoardSize):
            boardcolor = self.ZenGetBoardColor(j,i)
            if boardcolor == 0: #"."
                if t_b[i][j] ==2: black_territory+=1
                if t_w[i][j] ==1: white_territory+=1
            if boardcolor == 2: #"X"
                if t[i][j] >= -threshhold: black_alive+=1
                if t[i][j] < -threshhold: white_capture+=1
            if boardcolor == 1: #"O"
                if t[i][j] > threshhold: black_capture+=1
                if t[i][j] <= threshhold: white_alive+=1
      return black_alive, black_capture, black_territory, white_alive, white_capture, white_territory

    def ZenScore(self):
        black_prisoner=self.ZenGetNumBlackPrisoners()
        white_prisoner=self.ZenGetNumWhitePrisoners()
        Print('')
        Print("Black Passes: %3d    White Passes: %3d" % (self.blackpass, self.whitepass ))
        Print('level tb_wocap tw_wocap cap_b cap_w terr_b terr_w dead_b dead_w alive_b alive_w stone_b stone_w    result(terr,area)')
        t=self.ZenGetTerritoryStatictics()
        rt,ra=[0]*10,[0]*10
        for i in range(0,10,1):
            black_alive, black_capture, black_territory, white_alive, white_capture, white_territory=self.stat_territory(i*100,t)
            #Japanese rule
            black_score_territory = black_territory + 2*black_capture + black_prisoner
            white_score_territory = white_territory + 2*white_capture + white_prisoner
            result_score_territory = black_score_territory - white_score_territory
            
            #Chinese rule
            black_score_area = black_alive + black_capture + black_territory
            white_score_area = white_alive + white_capture + white_territory
            result_score_area = black_score_area - white_score_area
            
            rt[i]=result_score_territory-self.Komi
            ra[i]=result_score_area-self.Komi

            Print('%5d %8d %8d %5d %5d %6d %6d %6d %6d %7d %7d %7d %7d %4d %4d %6.1f %6.1f' % (i*100, \
                black_territory,white_territory, \
                black_capture, white_capture, \
                black_territory+black_capture, white_territory+white_capture, \
                black_capture+black_prisoner, white_capture+white_prisoner, \
                black_alive, white_alive, \
                black_alive+white_capture+white_prisoner, white_alive+black_capture+black_prisoner, \
                result_score_territory, result_score_area, \
                result_score_territory-self.Komi, result_score_area-self.Komi))

        i=3
        if rt[i]>0 : str='B+%.1f' % rt[i]
        else: str='W+%.1f' % -rt[i]
        return rt[i],str

    def gen_analyze(self, wsock, C=-1, interval=100):
        global X, Y, P, W, S
        print "zen7 thread %s is running" % threading.current_thread().name
        print wsock, C, interval
        print

        if C==-1: C=self.ZenGetNextColor()
        self.analyzeStatus = True
        self.lastStrength=self.Strength
        self.Strength=1000000

        list=[]
        thinkcount=0
        ret={"cmd":"", "para":"", "result":""}
        ret["cmd"]="lz-analyze";
        self.ZenStartThinking(C)
        while 1:
            thinkcount+=1
            time.sleep(self.ThinkInterval)
            list=self.GetTopMoveList(5)
            if len(list)==0:
                #Print('P.value==0')
                continue

            #Print('')
            #PrintAnalyze(list)
            listlen=len(list)
            re = []
            #analyz_response={"x":-1, "y":-1, "move":"", "visits":1, "winrate":1, "order":1, "pv":""}
            analyz_response=[dict() for i in range(listlen)]
            info=''
            for i in range(0, listlen):
            #for item in list:
                item = list[i]
                #Print('info move %s visits %d winrate %d order %d pv %s' % (item[4].split()[0], item[2], item[3] * 10000, i, item[4]))
                analyz_response[i]["x"] = 'ABCDEFGHJKLMNOPQRST'.find(item[4].split()[0][0])
                analyz_response[i]["y"] = self.BoardSize - int(item[4].split()[0][1:])
                analyz_response[i]["move"] = item[4].split()[0]
                analyz_response[i]["visits"] = item[2]
                analyz_response[i]["winrate"] = int(item[3] * 10000)
                analyz_response[i]["order"] = i
                analyz_response[i]["pv"] = item[4]
                #print analyz_response
                re.append(analyz_response[i])

                info+='info move %s visits %d winrate %d order %d pv %s ' % (analyz_response[i]["move"],analyz_response[i]["visits"],analyz_response[i]["winrate"],analyz_response[i]["order"], analyz_response[i]["pv"])
                    
            if info!='' and ((self.ThinkInterval*thinkcount*100)%interval)==0:
                #info move K19 visits 2 winrate 5114 order 0 pv K19 L3
                #Print(info)
                print ret
                print

            ret["result"]=re;
            #Print('')

            if self.ZenIsThinking() == -0x80000000:
                Print('ZenIsThinking()==-0x80000000')
                self.Strength = self.lastStrength
                break
            if self.analyzeStatus==0:
                Print('analyzeStatus==0')
                self.Strength = self.lastStrength
                break
            if list[0][2]>=self.Strength:
                Print('Stop gen_analyze >=Strength(%d)' % self.Strength)
                self.Strength = self.lastStrength
                self.analyzeStatus=0
                break
            
            if wsock!=0 and ((self.ThinkInterval*thinkcount*100)%interval)==0:
                try:
                    wsock.send(json.dumps(ret))
                except WebSocketError:
                    print 'web socket error'
                    self.analyzeStatus=0
                    break

        self.ZenStopThinking()
        #print "thread %s ended" % threading.current_thread().name
        return

    def loadsgf(self, filename, loadgamelen):
        Print('loadsgf: %s' % filename)
        Print('load gamelen: %d' % loadgamelen)
        try:
            fd=open(filename,'rb')
            str=fd.read()
            fd.close()
        except :
            print("File is not found.")
            return

        #get move from sgf
        gameinfostr = str[str.find(';'):str.find(';',str.find(';')+1)]
        #Print('gameinfo: %s' % gameinfostr)
        gameinfostr = gameinfostr.replace('\r','')
        gameinfostr = gameinfostr.replace('\n','')
        gameinfostr = gameinfostr.replace(';','')
        #gameinfostr = gameinfostr.replace('[','')
        gameinfostr=gameinfostr.split(']')
        #Print("gameinfostr: %s" % gameinfostr)

        self.ZenClearBoard()
        gameinfo=[]
        for i in range(0, len(gameinfostr)):
            gameinfo.append(gameinfostr[i].split('['))
            if gameinfo[i][0]=="SZ":
                self.BoardSize = int(gameinfo[i][1])
                self.ZenSetBoardSize(self.BoardSize)
            elif gameinfo[i][0]=="KM":
                self.Komi = float(gameinfo[i][1])
                self.ZenSetKomi(c_float(self.Komi))
            elif gameinfo[i][0]=="HA":
                self.Handicap = int(gameinfo[i][1])
                if (self.Handicap!=0):
                    self.ZenFixedHandicap(self.Handicap)
            elif gameinfo[i][0]=="PB":
                self.PlayerBlack = gameinfo[i][1]
            elif gameinfo[i][0]=="PW":
                self.PlayerWhite = gameinfo[i][1]
            elif gameinfo[i][0]=="RE":
                self.ResultStr = gameinfo[i][1]
            else:
                #Print('unknown gameinfo %s %s' % (gameinfo[i][0], ''if len(gameinfo[i])==1 else gameinfo[i][1]))
                pass

        #Print("gameinfo: %s" % gameinfo)
        #1.find main variation: replace all(, find the 1st ) as end
        movestr=str[str.find(';',str.find(';')+1):-1]
        movestr = movestr.replace('\r','')
        movestr = movestr.replace('\n','')
        movestr=movestr.replace('(','')
        if movestr.find(')') != -1:
            movestr = movestr[0:movestr.find(')')]
        str = movestr

        str=str.replace(';',"")
        str=str.replace('[',"")
        str=str.split(']')
        self.playlist=[]
        self.Sgf = []

        self.gamelen = 0
        for N in range(0, len(str)-1):
          if str[N][0]=='B':
            color = 2
          elif str[N][0]=='W':
            color = 1
          else:
            Print('unknown move %s' % str[N][0])
            continue
          
          if len(str[N])==3:
            self.playlist.append(['abcdefghijklmnopqrst'.find(str[N][1]), 'abcdefghijklmnopqrst'.find(str[N][2]),color])
            if ((int(N)<4) or (len(str)-int(N)<6)):
                Print('No:%3d %s SGF:%s%s Zen:%2d,%2d(%1d) GTP:%s%d' % (N+1, \
                    str[N][0], str[N][1], str[N][2], \
                    self.playlist[self.gamelen][0], self.playlist[self.gamelen][1], self.playlist[self.gamelen][2], \
                    'ABCDEFGHJKLMNOPQRST'[self.playlist[self.gamelen][0]],self.BoardSize-self.playlist[self.gamelen][1]) )

            if (str[N][1]!='t' and str[N][2]!='t'):
                ret = self.ZenPlay(self.playlist[self.gamelen][0], self.playlist[self.gamelen][1], self.playlist[self.gamelen][2])
                self.Sgf.append(str[N][0]+'['+str[N][1]+str[N][2]+']')
                if (color==2): self.blackcount+=1
                else: self.whitecount+=1
                self.passcount=0
            else:
                ret = self.ZenPass(color)
                if (color==2): self.blackpass+=1
                else: self.whitepass+=1
                self.passcount+=1
                self.Sgf.append(str[N][0]+'[tt]')
          else:
            self.playlist.append([self.BoardSize, self.BoardSize, color])
            if ((int(N)<4) or (len(str)-int(N)<6)):
                Print('No:%3d %s SGF:-,- Zen:%2d,%2d(%1d) GTP:-,-' % (N+1, \
                    str[N][0], self.playlist[self.gamelen][0], self.playlist[self.gamelen][1], self.playlist[self.gamelen][2]))
            ret = self.ZenPass(color)
            if (color==2): self.blackpass+=1
            else: self.whitepass+=1
            self.passcount+=1
            self.Sgf.append(str[N][0]+'[tt]')

          if not ret:
            Print("No: %3d ret = %s-%d" % (N+1, 'true' if ret else 'false', ret))

          self.gamelen+=1
          if(self.gamelen==loadgamelen) : break
        #zliu: add to Sgf=xx

        Print('')
        Print("BoardSize: %d Komi %.1f Handicap %d" % (self.BoardSize, self.Komi, self.Handicap))
        Print(u"Black: %s White: %s" % (self.PlayerBlack, self.PlayerWhite))
        Print("Total move: %d" % int(self.gamelen))
        Print("Result: %s" % self.ResultStr)
        Print('')
        #Print(self.final_score())
        r,s=self.ZenScore()
        Print('')
        Print(s)

        self.gamestr = str
        #Print('')
        #print 'playlist:', self.playlist
        #print 'sgf:', self.Sgf
        #print 'passcount:', self.passcount
        #print 'gamelen:', self.gamelen
        #print 'gamestr:', self.gamestr

    def rotate(self, symmetry):
        if len(self.playlist) == 0 :
          Print('please loadsgf first')
          return

        self.Sgf = []
        self.ZenClearBoard()
        playlist = self.playlist
        str = self.gamestr
        for N in range(0, len(self.playlist)-1):
          if symmetry == 1:
            tmp = playlist[N][0]
            playlist[N][0] = playlist[N][1]
            playlist[N][1] = tmp
          elif symmetry == 2:
            tmp = playlist[N][0]
            playlist[N][0] = -playlist[N][1]+18
            playlist[N][1] = tmp
          elif symmetry == 3:
            playlist[N][0] = -playlist[N][0]+18
            #playlist[N][1] = playlist[N][1]
          elif symmetry == 4:
            playlist[N][0] = -playlist[N][0]+18
            playlist[N][1] = -playlist[N][1]+18
          elif symmetry == 5:
            tmp = playlist[N][0]
            playlist[N][0] = -playlist[N][1]+18
            playlist[N][1] = -tmp+18
          elif symmetry == 6:
            tmp = playlist[N][0]
            playlist[N][0] = playlist[N][1]
            playlist[N][1] = -tmp+18
          elif symmetry == 7:
            #playlist[N][0] = playlist[N][0]
            playlist[N][1] = -playlist[N][1]+18
          str[N] = str[N][0]+'abcdefghijklmnopqrstuvwxyz'[playlist[N][0]]+'abcdefghijklmnopqrstuvwxyz'[playlist[N][1]]
          ret = self.ZenPlay(playlist[N][0], playlist[N][1], playlist[N][2])
          self.Sgf.append(str[N][0]+'['+str[N][1]+str[N][2]+']')
          self.passcount=0

    def play(self, colorstr, movestr):
        #print 'play %s %s' % (colorstr, movestr)
        C = self.ZenGetNextColor()
        if movestr == 'pass':
            if [C, colorstr] in [[1, 'b'], [2, 'w']]:
                self.ZenPass(C)
                self.passcount+=1
                if C==2 : self.blackpass+=1
                else:     self.whitepass+=1
                self.Sgf.append(('W' if C == 1 else 'B') + '[tt]')
                self.playlist.append([self.BoardSize, self.BoardSize, C])
                C = 3 - C
            self.ZenPass(C)
            self.passcount+=1
            if C==2 : self.blackpass+=1
            else:     self.whitepass+=1
            self.Sgf.append(('W' if C == 1 else 'B') + '[tt]')
            self.playlist.append([self.BoardSize, self.BoardSize, C])
            return
        
        x = 'abcdefghjklmnopqrstuvwxyz'.find(movestr[0])
        y = self.BoardSize - int(movestr[1:])

        if [C, colorstr] in [[1, 'b'], [2, 'w']]:
            self.ZenPass(C)
            self.passcount+=1
            if C==2 : self.blackpass+=1
            else:     self.whitepass+=1
            self.Sgf.append(('W' if C == 1 else 'B') + '[tt]')
            self.playlist.append([self.BoardSize, self.BoardSize, C])
            C = 3 - C 
        if C==2 : self.blackcount+=1
        else:     self.whitecount+=1
        self.ZenPlay(x, y, C)
        self.Sgf.append(('W' if C == 1 else 'B') +  '[' + 'abcdefghijklmnopqrstuvwxyz'[x] + 'abcdefghijklmnopqrstuvwxyz'[y] + ']')
        self.passcount=0
        self.playlist.append([x, y, C])

def Reply(S):
    sys.stdout.write('= ' + S + '\n\n')
    sys.stdout.flush()

def Print(S):
    sys.stderr.write(S + '\n')
    sys.stderr.flush()

def Help():
    Print("Allowed options:")
    Print(" -h [ --help ]".ljust(32) + "Show all allowed options.")
    Print(" -t [ --threads ] arg (=1)".ljust(32) + "Set the number of threads.")
    Print(" -s [ --strength ] arg (=10000)".ljust(32) + "Set the playing strength.")
    Print(" --size arg (=19)".ljust(32) + "Set the board size.")
    Print(" --komi arg (=7.5)".ljust(32) + "Set the komi.")
    Print(" -r [ --resign ] arg (=0.1)".ljust(32) + "Set the resign rate.")
    Print(" --interval arg (=0.1s)".ljust(32) + "Set the print interval.")
    Print(" -d [ --dll ] arg (=.\Zen.dll)".ljust(32) + "Set the path of Zen.dll.")
    sys.exit()

def main(argv=None):
    if argv is None:
        argv = sys.argv
        
    try: opts, args = getopt.getopt(sys.argv[1:], "ht:s:r:d:", ["help", "threads=", "strength=","size=","komi=","resign=","interval=","dll="])
    except getopt.GetoptError: Help()

    if args != []: Help()

    BoardSize=19
    Komi=7.5
    Strength=15000
    ZenDLL='d:\go\zen7\Zen.dll'
    Threads=4
    ResignRate=0.1
    ThinkInterval=0.1
    PrintInterval=1

    for opt, arg in opts:
        if opt in ['-h','--help']: Help()
        if opt in ['-t','--threads']:
            if not arg.isdigit() or int(arg) < 1: Help()
            Threads = int(arg)
            continue
        if opt in ['-s','--strength']:
            if not arg.isdigit() or int(arg) < 1: Help()
            Strength = int(arg)
            continue
        if opt in ['--size']:
            if not arg.isdigit() or int(arg) < 5 or int(arg) > 19: Help()
            BoardSize = int(arg)
            continue
        if opt in ['--komi']:
            try:
                Komi = float(arg)
            except ValueError:
                Help()
            continue
        if opt in ['-r','--resign']:
            try:
                ResignRate = float(arg)
            except ValueError:
                Help()
            continue
        if opt in ['--interval']:
            try:
                PrintInterval = float(arg)
            except ValueError:
                Help()
            continue
        if opt in ['-d','--dll']:
            if arg[-7:].lower() != 'zen.dll': Help()
            ZenDLL = arg
            continue
        Help()

    Z=ZEN(ZenDLL,BoardSize, Komi, Strength, Threads, ResignRate, ThinkInterval, PrintInterval)

    while True:
        Cmd = raw_input('').lower().split()

        if len(Cmd)==0:
            Z.analyzeStatus = 0
            Reply('')
            continue

        if Cmd[0] == 'quit':
            break

        if Cmd[0] == 'list_commands':
            Reply('name\n' + 'version\n' + 'quit\n' + 'known_command\n' + 'list_commands\n' + \
                'quit\n' + 'boardsize\n' + 'clear_board\n' + 'komi\n' + 'play\n' + 'genmove\n' + \
                'showboard\n' + 'undo\n' + 'pass\n'  + 'genmove\n' + 'protocol_version\n' + \
                'strength\n' + 'maxtime\n' + 'rotate\n' + 'zen-analyze\n' + 'loadsgf\n' + \
                'printsgf\n' + 'savesgf\n' + 'time_settings\n' + 'lz-analyze\n' + 'time_left\n' + \
                'fixed_handicap\n' + 'final_score\n' + 'analyze\n' + 'go\n' + 'auto\n' + \
                'policy\n' + 'territory\n' + 'gogui-analyze_commands\n' + \
                'sabaki-genmovelog\n' + 'sabaki-flat\n')
            continue

        if Cmd[0] == 'clear_board':
            Z.clear()
            Reply('')
            continue

        if Cmd[0] == 'boardsize':
            if ((len(Cmd)==1) or (not Cmd[1].isdigit())) :
                Print('BoardSize: %d' % Z.BoardSize)
                Reply('')
                continue
            Print('BoardSize: %d -> %d' % (Z.BoardSize, int(Cmd[1])) )

            Z.BoardSize = int(Cmd[1])
            Z.ZenSetBoardSize(Z.BoardSize)
            Reply('')
            continue

        if Cmd[0] == 'komi':
            if (len(Cmd)==1):
                Print('Komi: %.1f' % float(Z.Komi) )
                Reply('')
                continue
            Print('Komi: %.1f -> %.1f' % (Z.Komi, float(Cmd[1])) )

            Z.Komi = float(Cmd[1])
            Z.ZenSetKomi(c_float(Z.Komi))
            Reply('')
            continue

        if Cmd[0] == 'printsgf':
            Print('(;CA[UTF-8]GM[1]FF[4]DT[]AP[Zen7]SZ[%d]KM[%.1f]HA[%d]PB[%s]PW[%s]RE[%s]' % (Z.BoardSize, \
                Z.Komi, Z.Handicap, Z.PlayerBlack, Z.PlayerWhite, Z.ResultStr) +\
                ('' if Z.Sgf == [] else ';') + ';'.join(Z.Sgf) + ')')
            Print('')
            Reply('')
            continue

        if Cmd == ['version']:
            Reply(Z.version)
            continue

        if Cmd == ['protocol_version']:
            Reply('2')
            continue

        if Cmd == ['name']:
            Reply(Z.name)
            continue

        if Cmd == ['showboard']:
            Reply('')
            Z.showboard()
            continue

        if Cmd[0] == 'strength':
            if (len(Cmd)==1) :
              Print('Strength: %d (counts, NN eval)' % Z.Strength)
              Reply('')
              continue
            Print('Strength: %d -> %d (counts, NN eval)' % (Z.Strength,int(Cmd[1])))
            Z.Strength = int(Cmd[1])
            Reply('')
            continue

        if Cmd[0] == 'play':
            if not len(Cmd)==3:
                Print('wrong format')
                Reply('')
                continue
            if not Cmd[1]=='b' and not Cmd[1]=='w':
                Print('wrong color')
                Reply('')
                continue
            Z.play(Cmd[1], Cmd[2])
            Reply('')
            continue

        if Cmd in [['genmove', 'w'],['genmove', 'b']]:
            C = Z.ZenGetNextColor()
            if [C, Cmd[1]] in [[1, 'b'], [2, 'w']]:
                Z.ZenPass(C)
                Z.passcount+=1
                Z.Sgf.append(('W' if C == 1 else 'B') + '[tt]')
                C = 3 - C 
            Top = Z.ZenGenMove(C)
            if len(Top) != 0 and Top[0][3] < Z.ResignRate:
                Reply('resign')
            elif len(Top) == 0 or not Z.ZenPlay(Top[0][0], Top[0][1], C): 
                Z.ZenPass(C)
                Z.Sgf.append(('W' if C == 1 else 'B') + '[tt]')
                Z.passcount+=1
                Reply('pass')
            else:
                if (len(Top)==1): Top.append([-1,-1,0,0.0,''])
                Z.Sgf.append(('W' if C == 1 else 'B') +  '[' + 'abcdefghijklmnopqrstuvwxyz'[Top[0][0]] + 'abcdefghijklmnopqrstuvwxyz'[Top[0][1]] + ']\nC[%.2f %s\n%.2f %s]' % (Top[0][3] * 100, Top[0][4], Top[1][3] * 100, Top[1][4]))
                Z.passcount=0
                Reply(Top[0][4].split()[0])
            continue  

        if Cmd == ['go']:
            C = Z.ZenGetNextColor()
            Top = Z.ZenGenMove(C)
            if len(Top) != 0 and Top[0][3] < Z.ResignRate:
                Reply('resign')
            elif len(Top) == 0 or not Z.ZenPlay(Top[0][0], Top[0][1], C): 
                Z.ZenPass(C)
                Z.passcount+=1
                Z.Sgf.append(('W' if C == 1 else 'B') + '[tt]')
                Z.playlist.append([BoardSize, BoardSize, C])
                Reply('pass')
            else:
                if (len(Top)==1): Top.append([-1,-1,0,0.0,''])
                Z.Sgf.append(('W' if C == 1 else 'B') +  '[' + 'abcdefghijklmnopqrstuvwxyz'[Top[0][0]] + 'abcdefghijklmnopqrstuvwxyz'[Top[0][1]] + ']\nC[%.2f %s\n%.2f %s]' % (Top[0][3] * 100, Top[0][4], Top[1][3] * 100, Top[1][4]))
                Z.playlist.append([Top[0][0],Top[0][1],C])
                Z.passcount=0
                Reply(Top[0][4].split()[0])
            continue

        if Cmd == ['auto']:
            while 1:
                C = Z.ZenGetNextColor()
                Top = Z.ZenGenMove(C)
                if len(Top) != 0 and Top[0][3] < Z.ResignRate:
                    Reply('resign')
                    break
                elif len(Top) == 0 or not Z.ZenPlay(Top[0][0], Top[0][1], C): 
                    Z.ZenPass(C)
                    Z.passcount+=1
                    Z.Sgf.append(('W' if C == 1 else 'B') + '[]')
                    Z.playlist.append([Z.BoardSize, Z.BoardSize, C])
                    Reply('pass')
                    if Z.passcount==2:break
                    else:continue
                else:
                    if (len(Top)==1): Top.append([-1,-1,0,0.0,''])
                    Z.Sgf.append(('W' if C == 1 else 'B') +  '[' + 'abcdefghijklmnopqrstuvwxyz'[Top[0][0]] + 'abcdefghijklmnopqrstuvwxyz'[Top[0][1]] + ']\nC[%.2f %s\n%.2f %s]' % (Top[0][3] * 100, Top[0][4], Top[1][3] * 100, Top[1][4]))
                    #Sgf.append(('W' if C == 1 else 'B') +  '[' + 'abcdefghijklmnopqrstuvwxyz'[Top[0][0]] + 'abcdefghijklmnopqrstuvwxyz'[Top[0][1]] + ']N[%.2f]' % (Top[0][3] * 100))
                    Z.passcount=0
                    Z.playlist.append([Top[0][0],Top[0][1],C])
                    Z.passcount=0
                    Reply(Top[0][4].split()[0])
                continue
            Reply(Z.final_score())

        if Cmd == ['gogui-analyze_commands']:
            str = 'gfx/Policy/policy' + '\n' + \
                'gfx/Territory/territory' + '\n' + \
                'gfx/Analysis for Black/test' + '\n' + \
                'gfx/Analysis for White/test' + '\n' + \
                'gfx/Analysis one step/analyzeone'
            Reply(str)
            continue

        if Cmd == ['test']:
            str = '\n' + 'COLOR #BF4040 R16' + '\n' + 'COLOR #FF0000 Q16' + '\n' + 'LABEL Q16 Q16' + '\n' + 'LABEL R16 R16'
            Reply(str)
            time.sleep(2)
            str = '\n' + 'COLOR #BF4040 R4' + '\n' + 'COLOR #FF0000 Q4' + '\n' + 'LABEL Q4 52' + '\n' + 'LABEL R4 46'
            Reply(str)
            continue

        # http://www.sioe.cn/yingyong/yanse-rgb-16/
        colorlevel = ['#FF0000','#FF4500','#FFFF00','#7CFC00','#0000FF']
        #colorlevel = ['#FF0000','#FF4500','#FFFF00','#7CFC00','#0000FF']
        if Cmd[0] == 'analyze':
            if len(Cmd)==1:
                Print('Please use command: analyzeone')
                Reply('')
                continue
            playlist = Z.playlist
            playlen = len(playlist)
            
            if Cmd[1]=='all':
                begin=0
                end=playlen
            elif len(Cmd)!=3:
                Print('Only support 3 commands')
                Print('1. analyze all')
                Print('2. analyze begin end')
                Print('3. analyze')
                Reply('')
                continue
            else:
                begin = int(Cmd[1])
                end = int(Cmd[2])

            result = []
            if playlen==0:
                Print('please loadsgf first')
            Z.clear()
            for i in range(0, playlen):
                Top = []
                rt=0.0
                rtstr='--'
                if (i+1)>=begin and (i+1)<=end:
                    Top = Z.ZenGenMove(playlist[i][2])
                    rt,rtstr=Z.ZenScore()
                Z.ZenPlay(playlist[i][0], playlist[i][1], playlist[i][2])
                
                if len(Top)==0:
                    result.append([-1,-1,0,0,'PASS',rt,rtstr,0])
                else:
                    if playlist[i][2]==2:
                        result.append([Top[0][0],Top[0][1],Top[0][2],Top[0][3],Top[0][4],rt,rtstr,0])
                    else:
                        result.append([Top[0][0],Top[0][1],Top[0][2],1-Top[0][3],Top[0][4],rt,rtstr,0])

            Print('')
            Print(' no color kifu zen7 count    rate   delta  score   result seq')
            for i in range(0, len(result)):
                if (i+1)<begin or (i+1)>end:
                    continue
                if i<(len(result)-1):
                    result[i][7]=result[i+1][3]-result[i][3]
                else:
                    result[i][7]=0.0
                if playlist[i][0]==Z.BoardSize:
                    tmpstr = 'PASS'
                else:
                    tmpstr = '%s%d' % ('ABCDEFGHJKLMNOPQRST'[playlist[i][0]], Z.BoardSize-playlist[i][1])
                Print('%3d %5s %4s %4s %5d %6.2f%% %6.2f%% %6.1f %8s %s' % (i+1, \
                    'B' if playlist[i][2]==2 else 'W', \
                    tmpstr, \
                    result[i][4].split()[0], \
                    result[i][2], \
                    result[i][3]*100, \
                    result[i][7]*100, \
                    result[i][5], \
                    result[i][6], \
                    result[i][4]))

            Z.playlist = playlist
            Reply('')
        
        if Cmd == ['analyzeone']:
            C = Z.ZenGetNextColor()
            Print('analyzeone next color: %s' % 'Black' if C==2 else 'White')
            Top = Z.ZenGenMove(C)
            print 'Top: ', Top
            if len(Top) != 0 and Top[0][3] < Z.ResignRate:
              Print('resign')
            elif len(Top) == 0 :#or not ZenPlay(Top[0][0], Top[0][1], C): 
              #ZenPass(C)
              #passcount+=1
              #Sgf.append(('W' if C == 1 else 'B') + '[tt]')
              #playlist.append([19, 19, C])
              Print('pass')
            else:
              #Sgf.append(('W' if C == 1 else 'B') +  '[' + 'abcdefghijklmnopqrstuvwxyz'[Top[0][0]] + 'abcdefghijklmnopqrstuvwxyz'[Top[0][1]] + ']N[%.2f]' % (Top[0][3] * 100))
              #playlist.append([Top[0][0],Top[0][1],C])
              #passcount=0
              Print(('W' if C == 1 else 'B') +  '[' + 'abcdefghijklmnopqrstuvwxyz'[Top[0][0]] + 'abcdefghijklmnopqrstuvwxyz'[Top[0][1]] + ']N[%.2f]' % (Top[0][3] * 100))
              Print(Top[0][4].split()[0])
            
            str = ''
            for i in range(0, len(Top)):
              str += '\nCOLOR %s %s' % (colorlevel[i], Top[i][4].split()[0])
              str += '\nLABEL %s %.1f' % (Top[i][4].split()[0], Top[i][3]*100)
            Reply(str)
            continue

        if Cmd == ['policy']:
            #t=ZenGetPolicyKnowledge()
            #print19(t)

            t = np.array(Z.ZenGetPolicyKnowledge())
            r = 1000.0/9
            #r = (t.max()-t.min())/9
            #m = -t.min()
            alllist=[]
            for i in range(0, Z.BoardSize):
              listbefore, listafter=[],[]
              prn=''
              for j in range(0, Z.BoardSize):
                listbefore.append('%5d' % t[i][j] )
                if t[i][j] <=0 :
                  listafter.append('0')
                else:
                  listafter.append('%d' % ((t[i][j])/r))
              prn = ' '.join(listbefore) + ' ->  ' + ' '.join(listafter)
              alllist.append('['+','.join(listafter)+']')
              print(prn)
            Reply('#sabaki{"variations":"","heatmap":[%s]}'%','.join(alllist))

            #Reply('')
            continue

        if Cmd == ['territory']:
            t1 = Z.ZenGetTerritoryStatictics()
            #Z.print19(t1)
            #print
            
            t = np.array(t1)
            r = 999.0/9
            alllist=[]
            for i in range(0, Z.BoardSize):
              listbefore, listafter=[],[]
              prn=''
              for j in range(0, Z.BoardSize):
                listbefore.append('%4d' % t[i][j] )
                if (t[i][j] <=500) and (t[i][j] >=-500):
                  listafter.append('%d' % 0)
                else:
                  listafter.append('%d' % ((t[i][j])/r))
              prn = ' '.join(listbefore) + ' ->  ' + ' '.join(listafter)
              alllist.append('['+','.join(listafter)+']')
              print(prn)

            Reply('#sabaki{"variations":"","heatmap":[%s]}'%','.join(alllist))
            #Reply('')
            continue

        # sabaki genmove log flat format
        '''
            = #sabaki{
          "variations":"
          (;C[- `43` visits\n  - **V** `49.84%`\n  - **N** `17.58%`]AB[dd][pd][cp][dq]AW[pp][dp][cq]LB[dd:1][pp:2][pd:3][dp:4][cp:5][cq:6][dq:7])
          ...
          ","heatmap":[
            [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
          ... 17 times
            [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]]
          }
        '''
        # none flat mode
        '''
          = #sabaki{"variations":"
          (;C[- `40` visits\n  - **V** `49.52%`\n  - **N** `17.72%`]B[pd];W[dp];B[dd];W[pp];B[qp];W[qq];B[qo])
          ...
          "}
        '''
        if Cmd == ['sabaki-flat']:
            Z.SabakiFlat=not Z.SabakiFlat
            Print('Sabaki Flat: %d -> %d' % (not Z.SabakiFlat, Z.SabakiFlat) )
            Reply('')
            continue
        if Cmd == ['sabaki-genmovelog']:
            nc = Z.ZenGetNextColor()
            if nc ==2:
              nc=1
            else:
              nc=2
            t = np.array(Z.ZenGetPolicyKnowledge())
            r = 1000.0/9
            #r = (t.max()-t.min())/9
            #m = -t.min()
            alllist=[]
            for i in range(0, Z.BoardSize):
              listbefore, listafter=[],[]
              prn=''
              for j in range(0, Z.BoardSize):
                if t[i][j] <=0 :
                  listafter.append('0')
                else:
                  listafter.append('%d' % ((t[i][j])/r))
              alllist.append('['+','.join(listafter)+']')
            
            #print(Top[0][0],Top[0][1],Top[0][2],Top[0][3],Top[0][4])
            if len(Top)==0:
              str = '#sabaki{"variations":"","heatmap":[%s]}' % (','.join(alllist) )
              Reply(str)
              continue
            
            #print(len(Top))
            seq = Top[0][4].split(' ')
            #print(seq)
            seqstr=[]
            # ** means bold font
            seqstr.append('(;C[- `%d` visits\\n  - **winrate** `%.1f%%`]N[%.1f%%]' % (Top[0][2],Top[0][3]*100,Top[0][3]*100) )
            for i in range(0,len(seq)):
              if len(seq[i])==0:continue
              zenx='ABCDEFGHJKLMNOPQRST'.find(seq[i][0])
              zeny=BoardSize-int(seq[i][1:])
              #print(i,'abcdefghijklmnopqrstuvwxyz'[zenx], 'abcdefghijklmnopqrstuvwxyz'[zeny])
              onestr='abcdefghijklmnopqrstuvwxyz'[zenx]+ 'abcdefghijklmnopqrstuvwxyz'[zeny]
              if Z.SabakiFlat:
                seqstr.append('A%s[%s]LB[%s:%d]' % ('B'if nc==2 else 'W',onestr,onestr,i+1) ) #flat
              else:
                seqstr.append(';%s[%s]' % ('B'if nc==2 else 'W',onestr) ) #without flat
              nc+=1
              if nc==3: nc=1
            seqstr.append(')')
            #print(seqstr)

            str = '#sabaki{"variations":"%s","heatmap":[%s]}' % (''.join(seqstr), ','.join(alllist) )
            Reply(str)

            continue

        if Cmd[0] == 'maxtime':
            if (len(Cmd)==1) :
                Print('MaxTime: %.1f' % Z.MaxTime)
                Reply('')
                continue
            Print('MaxTime: %.1f -> %.1f' % (Z.MaxTime, float(Cmd[1]))  )
            Z.MaxTime = float(Cmd[1])
            Z.ZenSetMaxTime(c_float(Z.MaxTime))
            Reply('')
            continue

        if Cmd[0] == 'loadsgf':
            if (len(Cmd)==1) :
                Print("Missing file name")
                Reply('')
                continue

            filename = Cmd[1]
            loadgamelen=-1
            if (len(Cmd)==3) :
                loadgamelen = int(Cmd[2])
            Z.loadsgf(filename, loadgamelen)

            Reply('')
            continue

        if Cmd[0] == 'savesgf':
            if (len(Cmd)==1) :
                Print("Missing file name")
                Reply('')
                continue

            filename = Cmd[-1]
            try:
              fd=open(filename,'wb')
            except :
              print("File open failed.")
              Reply('')
              continue

            fd.write('(;CA[UTF-8]GM[1]FF[4]DT[]AP[Zen7]SZ[%d]KM[%.1f]' % (BoardSize, Komi) + ('' if Sgf == [] else ';') + '\n;'.join(Sgf) + ')')
            fd.close()
            Reply('')
            continue

        if Cmd[0] == 'rotate':
            print '2 clockwise 90'
            print '4 clockwise 180'
            print '6 clockwise 270'
            print '3 mirror clockwise 0,   left-right symmetry'
            print '5 mirror clockwise 90'
            print '7 mirror clockwise 180'
            print '1 mirror clockwise 270, center-symmetry'

            if not Cmd[-1].isdigit():
                print('Missing parameter to rotate')
                Reply('')
                continue

            symmetry = int(Cmd[-1])
            Z.rotate(symmetry)
            Reply('')
            continue

        if Cmd == ['final_score']:
            Print('')
            Print('(;CA[UTF-8]GM[1]FF[4]DT[]AP[Zen7]SZ[%d]KM[%.1f]HA[%d]PB[%s]PW[%s]RE[%s]\n' % (Z.BoardSize, Z.Komi, Z.Handicap, Z.PlayerBlack, Z.PlayerWhite, Z.ResultStr) +\
              ('' if Z.Sgf == [] else ';') + '\n;'.join(Z.Sgf) + ')')
            Print('')
            Itemall = Z.Itemall
            for i in range(0, len(Itemall)):
                color=Itemall[i][0]
                list=Itemall[i][1][0] if Itemall[i][1] else [-1,-1,-1,0.0,'']
                lprv=Itemall[i][2][0] if Itemall[i][2] else [-1,-1,-1,0.0,'']
                Print('%3d %s (%2d,%2d %5d %2.2f%%) (%2d,%2d %5d %2.2f%%) %s' % (i+1,('W' if color== 1 else 'B'),\
                    list[0], list[1], list[2], list[3]*100,\
                    lprv[0], lprv[1], lprv[2], lprv[3]*100,\
                    list[4]) )
                list=Itemall[i][1][1] if len(Itemall[i][1])>1 else [-1,-1,-1,0.0,'']
                lprv=Itemall[i][2][1] if len(Itemall[i][2])>1 else [-1,-1,-1,0.0,'']
                Print('      (%2d,%2d %5d %2.2f%%) (%2d,%2d %5d %2.2f%%) %s' % (\
                    list[0], list[1], list[2], list[3]*100,\
                    lprv[0], lprv[1], lprv[2], lprv[3]*100,\
                    list[4]) )
            Print('')
            Reply(Z.final_score())
            continue

        if Cmd[0] == 'lz-analyze':
            if (len(Cmd)==1) :
                Print('Missing interval')
                Reply('')
                continue

            wsock=0
            C = Z.ZenGetNextColor()
            interval=int(Cmd[1])
            th = threading.Thread(target=Z.gen_analyze, args=(wsock,C,interval), name='gen-analyze')
            th.start()
            Reply('')
            continue

        if Cmd[0] == 'undo':
            if (len(Cmd)==1) :
              Reply('')
              continue
            Reply('')
            continue

        if Cmd[0] == 'time_settings':
            if (len(Cmd)==1) :
              Reply('')
              continue
            Reply('')
            continue

        if Cmd[0] == 'time_left':
            if (len(Cmd)==1) :
              Reply('')
              continue
            Reply('')
            continue

        if Cmd[0] == 'fixed_handicap':
            if (len(Cmd)==1) :
              Reply('')
              continue
            Reply('')
            continue

        ### others
        Reply('')

if __name__=="__main__":
    sys.exit(main())

