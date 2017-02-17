## Copyright 2017 Giorgio Pea <giorgio.pea@mail.polimi.it>
##
## Licensed under the Apache License, Version 2.0 (the "License");
## you may not use this file except in compliance with the License.
## You may obtain a copy of the License at
##
##     http://www.apache.org/licenses/LICENSE-2.0
##
## Unless required by applicable law or agreed to in writing, software
## distributed under the License is distributed on an "AS IS" BASIS,
## WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
## See the License for the specific language governing permissions and
## limitations under the License.

from __future__ import division
from collections import OrderedDict
import os
import csv
import sys


class Extractor:
    def __init__(self, directory, target_file, users, memory, containers, headerFlag):
        self.containers = containers
        self.appStartTime = None
        self.minTaskLaunchTime = 0
        self.users = users
        self.memory = memory
        self.jobCsvHeaders = ['run', 'jobId', 'CompletionTime','DeltaBeforeComputing']
        #This headers must be repetead as many times as the maximum number of stages
        #among all the jobs
        self.stagesCsvHeaders = ['nTask', 'maxTask', 'avgTask', 'SHmax', 'SHavg', 'Bmax', 'Bavg']
        ##
        self.terminalCsvHeaders = ['users', 'dataSize', 'nContainers']
        self.directory = directory
        self.directoryName = os.path.basename(directory)
        self.directoryName = self.directoryName[:len(self.directoryName) - 4]
        self.target_file = target_file
        self.stagesRows = None
        self.stagesTasksList = []
        self.jobsList = []
        self.maxStagesLenght = 0
        self.headerFlag = headerFlag

    """
    Writes the header of the csv file this python script produces
    """
    def writeHeader(self):
        with open(self.target_file, 'a') as f:
            writer = csv.writer(f, delimiter=',', lineterminator='\n')
            targetHeaders = []
            targetHeaders += self.jobCsvHeaders
            for i in range(0, self.maxStagesLenght):
                targetHeaders += self.stagesCsvHeaders
            targetHeaders += self.terminalCsvHeaders
            writer.writerow(targetHeaders)

    def produceFile(self, finalList):
        with open(self.target_file, 'a') as f:
            writer = csv.writer(f, delimiter=',', lineterminator='\n')
            for item in finalList:
                writer.writerow(item)

    def retrieveApplicationStartTime(self):
        with open(self.directory+"/app_1.csv","r") as f:
            app_rows = csv.DictReader(f)
            for index,row in enumerate(app_rows):
                if index==0:
                    self.appStartTime = int(row["Timestamp"])

    def retrieve_jobs(self, jobs_file):
        with open(jobs_file, "r") as f:
            targetList = []
            jobs_rows = sorted(csv.DictReader(f), key=lambda x: x["Job ID"])
            i = 0
            max_ = 0
            while i < len(jobs_rows):
                completionTime = int(jobs_rows[i + 1]["Completion Time"]) - int(jobs_rows[i]["Submission Time"])
                stages = jobs_rows[i]["Stage IDs"][1:(len(jobs_rows[i]["Stage IDs"]) - 1)].split(", ")
                if max_ < len(stages):
                    max_ = len(stages)
                targetList.append([jobs_rows[i]["Job ID"], completionTime, stages])
                i += 2
            self.maxStagesLenght = max_
        return targetList

    def computeMaxStageCardinality(self):
        return max(map(lambda x : len(x[2]),self.jobsList));

    def produce_final_list(self):
        currentLenght = 3;
        final_list = []
        tmp_list = []
        normalizedMaxStageCardinality = 4+self.maxStagesLenght*7
        for job in self.jobsList:
            tmp_list.append(self.directoryName)
            tmp_list.append(job[0])
            tmp_list.append(job[1])
            tmp_list.append(self.minTaskLaunchTime-self.appStartTime);
            for stageItem in self.stagesTasksList:
                if stageItem["stageId"] in job[2]:
                    tmp_list = tmp_list + stageItem.values()[1:]
            length = len(tmp_list);
            if length < normalizedMaxStageCardinality:
                for i in range(0, normalizedMaxStageCardinality - length):
                    tmp_list.append("")

            tmp_list.append(self.users)
            tmp_list.append(self.memory)
            tmp_list.append(self.containers)
            final_list.append(tmp_list)
            tmp_list = []
        return final_list

    def run(self):
        tasks_file = self.directory + "/tasks_1.csv"
        jobs_file = self.directory + "/jobs_1.csv"
        self.retrieveApplicationStartTime()
        with open(tasks_file, "r") as f:
            self.stagesRows = self.orderStages(csv.DictReader(f))
            self.minTaskLaunchTime = min(map(lambda x: int(x["Launch Time"]) , self.stagesRows))
        self.jobsList = self.retrieve_jobs(jobs_file)
        if self.headerFlag == 'True':
            self.writeHeader()
        self.buildstagesTasksList()
        self.produceFile(self.produce_final_list())

    """Checks the existence of the given file path"""

    def fileValidation(self, filename):
        if not (os.path.exists(filename)):
            print("The file " + filename + " does not exists")
            exit(-1)

    """Orders the stages dict by 'Stage Id'"""

    def orderStages(self, stages):
        return sorted(stages, key=lambda x: x["Stage ID"])

    def computeStagesTasksDetails(self, stageId, batch):
        shuffleBatch = []
        normalBatch = []
        bytesBatch = []
        for item in batch:
            normalBatch.append(item[0])
            shuffleBatch.append(item[1])
            bytesBatch.append(item[2])
        maxTask = max(normalBatch)
        maxShuffle = max(shuffleBatch)
        avgTask = reduce(lambda x, y: x + y, normalBatch) / len(normalBatch)
        avgShuffle = reduce(lambda x, y: x + y, shuffleBatch) / len(shuffleBatch)
        maxBytes = max(bytesBatch)
        avgBytes = reduce(lambda x, y: x + y, bytesBatch) / len(bytesBatch)
        targetDict = OrderedDict({})
        targetDict["stageId"] = stageId
        targetDict["nTask"] = len(batch)
        targetDict["maxTask"] = maxTask
        targetDict["avgTask"] = avgTask
        targetDict["SHmax"] = maxShuffle
        targetDict["SHavg"] = avgShuffle
        targetDict["Bmax"] = maxBytes
        targetDict["Bavg"] = avgBytes
        return targetDict

    def buildstagesTasksList(self):
        batch = []
        lastRow = None
        for row in self.stagesRows:
            if lastRow != None and lastRow["Stage ID"] != row["Stage ID"]:
                self.stagesTasksList.append(self.computeStagesTasksDetails(lastRow["Stage ID"], batch))
                batch = []
            if row["Shuffle Write Time"] == "NOVAL":
                batch.append([int(row["Executor Run Time"]), -1, -1])
            else:
                batch.append(
                    [int(row["Executor Run Time"]), int(row["Shuffle Write Time"]), int(row["Shuffle Bytes Written"])])

            lastRow = row
        self.stagesTasksList.append(self.computeStagesTasksDetails(lastRow["Stage ID"], batch))


def main():
    args = sys.argv
    if len(args) != 7:
        print("Required args: [TOP_DIRECTORY] [TARGET_FILE]")
        exit(-1)
    else:
        extractor = Extractor(str(args[1]), str(args[2]), str(args[3]), str(args[4]), str(args[5]),str(args[6]))
        extractor.run()


if __name__ == '__main__':
    main()
