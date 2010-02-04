-- phpMyAdmin SQL Dump
-- version 3.1.1
-- http://www.phpmyadmin.net
--
-- Host: localhost
-- Generation Time: Mar 03, 2009 at 03:59 PM
-- Server version: 5.0.58
-- PHP Version: 5.2.6

SET SQL_MODE="NO_AUTO_VALUE_ON_ZERO";

--
-- Database: `rqp`
--

-- --------------------------------------------------------

--
-- Table structure for table `files`
--

DROP TABLE IF EXISTS `files`;
CREATE TABLE `files` (
  `f_id` INT NOT NULL auto_increment,
  `p_record` INT NOT NULL,
  `files` text NOT NULL,
  `f_user` varchar(16) NOT NULL,
  `f_group` varchar(16) NOT NULL,
  `f_is_suid` tinyint DEFAULT 0,
  `f_is_sgid` tinyint DEFAULT 0,
  PRIMARY KEY  (`f_id`),
  KEY `rec` USING BTREE (`p_record`)
) ENGINE=MyISAM AUTO_INCREMENT=1 DEFAULT CHARSET=latin1 ;

-- --------------------------------------------------------

--
-- Table structure for table `packages`
--

DROP TABLE IF EXISTS `packages`;
CREATE TABLE IF NOT EXISTS `packages` (
  `p_record` INT NOT NULL auto_increment,
  `p_tag` text NOT NULL,
  `p_package` text NOT NULL,
  `p_version` text NOT NULL,
  `p_release` text NOT NULL,
  `p_date` text NOT NULL,
  `p_arch` varchar(10) NOT NULL,
  PRIMARY KEY  (`p_record`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1 AUTO_INCREMENT=1 ;

-- --------------------------------------------------------

--
-- Table structure for table `provides`
--

DROP TABLE IF EXISTS `provides`;
CREATE TABLE IF NOT EXISTS `provides` (
  `p_id` INT NOT NULL auto_increment,
  `p_record` INT NOT NULL,
  `provides` text NOT NULL,
  PRIMARY KEY  (`p_id`),
  KEY `rec` USING BTREE (`p_record`)
) ENGINE=MyISAM AUTO_INCREMENT=1 DEFAULT CHARSET=latin1;

-- --------------------------------------------------------

--
-- Table structure for table `requires`
--

DROP TABLE IF EXISTS `requires`;
CREATE TABLE IF NOT EXISTS `requires` (
  `r_id` INT NOT NULL auto_increment,
  `p_record` INT NOT NULL,
  `requires` text NOT NULL,
  PRIMARY KEY  (`r_id`),
  KEY `rec` USING BTREE (`p_record`)
) ENGINE=MyISAM AUTO_INCREMENT=1 DEFAULT CHARSET=latin1;

-- --------------------------------------------------------

--
-- Table structure for table `symbols`
--

DROP TABLE IF EXISTS `symbols`;
CREATE TABLE IF NOT EXISTS `symbols` (
  `s_id` INT NOT NULL auto_increment,
  `p_record` INT NOT NULL,
  `symbols` text NOT NULL,
  PRIMARY KEY  (`s_id`),
  KEY `rec` USING BTREE (`p_record`)
) ENGINE=MyISAM AUTO_INCREMENT=1 DEFAULT CHARSET=latin1;

-- --------------------------------------------------------

--
-- Table structure for table `tags`
--

DROP TABLE IF EXISTS `tags`;
CREATE TABLE IF NOT EXISTS `tags` (
  `tag` varchar(128) NOT NULL,
  `path` varchar(256) NOT NULL,
  `tdate` text NOT NULL,
  PRIMARY KEY  (`tag`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1;

