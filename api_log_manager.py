#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
检查ROS的日志占用，如果超过指定的数值，则删除指定日期之前的日志
"""

import os
import subprocess
import time
import threading
import glob
import datetime
import shutil
import uuid

def get_dir_space(directory):
    """获取目录占用的空间

    :param directory: 指定的目录
    :type directory: str
    :return: 目录占用的空间,单位为K
    """
    p = subprocess.Popen(['du %s -d0|cut  -f 1' % directory], shell=True, stdout=subprocess.PIPE)
    if p.wait():
        raise CUtilsException(SystemErrorCode.UNKNOWN, "获取目录占用空间失败!")
    ret = p.stdout.read()
    return int(ret)

class LogException(Exception):
    def __init__(self, error_code, message):
        self.args = (error_code, message)
        self.error_code = error_code
        self.message = message



class LogManager(object):
    """
    日志管理器, 管理记录的日志

    """

    def __init__( self, 
                  log_path, 
                  log_archive_path,
                  log_archive_name_prefix,
                  max_archive_size,
                  log_file_glob_pattern,
                  delete_until_percent,
                  log_packup_size_unit ):
        """
        :param log_path: 日志存储路径
        :param max_archive_size: maximum size for archive directory
        :param log_archive_path: 程序的日志存储路径
        :param log_file_glob_patterh: 日志文件过滤pattern
        """
        self.log_path = log_path
        self.log_archive_path = log_archive_path
        self.max_archive_size = max_archive_size
        self.log_file_glob_pattern = log_file_glob_pattern
        self.log_archive_name_prefix = log_archive_name_prefix
        self.delete_until_percent = delete_until_percent
        self.log_packup_size_unit = log_packup_size_unit

    def archive(self):
        """
        归档日志
        Assume that this runs before other program starts

        :return:
        """
        self.check_or_create_archive_path()
        os.chdir(self.log_path)
        log_files = glob.glob(self.log_file_glob_pattern)
        log_files_stamp = map(lambda x: (datetime.datetime.fromtimestamp(os.path.getmtime(x)),
                                         x),
                              log_files)
        log_files_stamp = map(lambda x: (x[0],
                                         "%04d%02d%02d"%(x[0].year,
                                                         x[0].month,
                                                         x[0].day),
                                         "%02d%02d%02d"%(x[0].hour,
                                                         x[0].minute,
                                                         x[0].second),
                                         x[1]),
                              log_files_stamp)
        log_files_stamp.sort(key=lambda e: e[0]) # small index for earlier
        print "log files: "
        print "\n".join(map(lambda x: x[1]+" "+x[2]+"  "+x[3],log_files_stamp))
        log_files_date_map = {}
        for x in log_files_stamp:
            if x[1] not in log_files_date_map:
                log_files_date_map[x[1]] = [x]
            else:
                log_files_date_map[x[1]].append(x)
            pass
        
        for x in log_files_date_map:
            print x
            temp_dir_name = "temp_pack_" + str(uuid.uuid4()) + "_"+x
            directory_to_pack = ( self.log_archive_name_prefix + 
                                  "__" + 
                                  x )
            os.makedirs( os.path.join( temp_dir_name ,
                                       directory_to_pack ) )
            self.fix_permission( temp_dir_name )

            for y in log_files_date_map[x]:
                filename = y[-1]
                print "   ", filename
                shutil.move( filename, 
                             os.path.join( os.path.join( temp_dir_name ,
                                                         directory_to_pack ) ,
                                           filename ) )
                pass
            pass

            pwd = self.get_pwd()
            os.chdir( temp_dir_name )

            self.pack( target_file = os.path.join( self.log_archive_path,
                                                   ( directory_to_pack + 
                                                     "__pack-" + 
                                                     datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + 
                                                     ".tar.gz" ) ),
                       path_to_pack = directory_to_pack )

            os.chdir( pwd )
            
            shutil.rmtree( temp_dir_name )

    def get_pwd(self):
        return os.path.abspath( os.path.curdir )

    def archive_cleanup_old(self):
        if (get_dir_space(self.log_archive_path) < self.max_archive_size ):
            return

        pwd = self.get_pwd()
        os.chdir(self.log_archive_path)

        archive_file_list = glob.glob( ( self.log_archive_name_prefix + 
                                         "*" ) )

        archive_files_stamp = map(lambda x: (datetime.datetime.fromtimestamp(os.path.getmtime(x)),
                                         x),
                                  archive_file_list)

        archive_files_stamp.sort( key = lambda e: e[0] )

        #print '\n'.join(map(repr,archive_files_stamp))

        discounted_max_archive_size = self.delete_until_percent * self.max_archive_size

        while ( get_dir_space(self.log_archive_path) > discounted_max_archive_size ):
            archive_to_delete = archive_files_stamp.pop()
            os.remove(archive_to_delete[1])

        os.chdir(pwd)


    def pack(self, target_file, path_to_pack ):
        """
        打包日志

        :param ros_log_dir:
        :return:
        """
        p = subprocess.Popen(['tar', 'czfP', target_file, path_to_pack])
        ret = p.wait()
        if ret:
            raise LogException('运行tar命令失败! log_file:%s, log_dir:%s' % (log_file, ros_log_dir))
            
            
    def fix_permission(self, path):
        for root, dirs, files in os.walk( path ):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0775)
            for f in files:
                os.chmod(os.path.join(root, f), 0664)

    def check_or_create_archive_path(self):
        path = self.log_archive_path
        if not os.path.exists( path ):
            os.makedirs( path )
            self.fix_permission(path)


    def start_web(self):
        """
        开启web服务器,可用于下载日志

        :return:
        """
        from BaseHTTPServer import HTTPServer
        from CGIHTTPServer import CGIHTTPRequestHandler
        os.chdir(self.log_archive_path)
        serv = HTTPServer(("", 8080), CGIHTTPRequestHandler)
        serv.serve_forever()

    def do(self):
        #self.clear()
        self.archive()
        self.archive_cleanup_old()
        #self.start_web()


def main():
    max_archive_size = 100 * 1024 # delete archived logs when size over 100 MB
    delete_until_percent = 0.75
    log_packup_size_unit = 100 * 1024 # pack up per 100 MB log files 
    log_rotator_api = LogManager( log_path = "/home/xlh/.ros/navigation_api_glog", 
                                  max_archive_size = max_archive_size,
                                  delete_until_percent = delete_until_percent,
                                  log_packup_size_unit = log_packup_size_unit,
                                  log_archive_name_prefix = "navigation_api_glog",
                                  log_archive_path = "/home/xlh/.ros/log_archive_glog/navigation_api_glog",
                                  log_file_glob_pattern = "*_log_*" )
    
    log_rotator_api.do()



if __name__ == '__main__':
    main()
