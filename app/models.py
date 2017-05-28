from peewee import *
from app import DATABASE_URI
from playhouse.db_url import connect
from collections import namedtuple


database    = connect(DATABASE_URI)

def create_tables():
    database.connect()
    database.create_tables([RPM_File, RPM_User, RPM_Group, RPM_Package, RPM_ProvidesIndex,
               RPM_ProvidesName, RPM_RequiresIndex, RPM_RequiresName,
               RPM_Symbols, RPM_Flags, RPM_Tag, RPM_AlreadySeen], True) # only create if it doesn't already exist


class BaseModel(Model):
    class Meta:
        database = database


# the binary rpm files model
class RPM_File(BaseModel):
    package_id = IntegerField()  # p_record
    tag_id     = IntegerField()  # t_record
    user_id    = IntegerField()  # u_record
    group_id   = IntegerField()  # g_record
    file       = TextField()     # files
    is_suid    = IntegerField(default=0)  # f_is_suid
    is_sgid    = IntegerField(default=0)  # f_is_sgid
    perms      = CharField()     # f_perms

    @classmethod
    def get_id(cls, file, tag_id, package_id):
        """
        Returns the file id for the provided file name, package record and tag record
        :param file: the file to lookup
        :param tag_id: the tag id to lookup
        :param package_id: the package id to lookup
        :return: int
        """
        file = RPM_File.get((RPM_File.file == file) & (RPM_File.package_id == package_id) & (RPM_File.tag_id == tag_id))
        return file.id

    def __repr__(self):
        return '<RPM File {self.file}>'.format(self=self)


# the binary rpm user model
class RPM_User(BaseModel):
    user = CharField(null=False)  # f_user

    @classmethod
    def get_id(cls, name):
        """
        Returns the user id for the provided user name
        :param name: the name to lookup
        :return: int
        """
        user = RPM_User.get(RPM_User.user == name)
        return user.id

    def __repr__(self):
        return '<RPM User {self.user}>'.format(self=self)


# the binary rpm group model
class RPM_Group(BaseModel):
    group = CharField(null=False)  # f_group

    @classmethod
    def get_id(cls, name):
        """
        Returns the group id for the provided group name
        :param name: the name to lookup
        :return: int
        """
        group = RPM_Group.get(RPM_Group.group == name)
        return group.id

    def __repr__(self):
        return '<RPM Group {self.group}>'.format(self=self)


# the binary rpm package model
class RPM_Package(BaseModel):
    tag_id   = CharField(null=False)  # t_record
    tag      = TextField(null=False)  # p_tag
    package  = TextField(null=False)  # p_package
    version  = TextField(null=False)  # p_version
    release  = TextField(null=False)  # p_release
    date     = TextField(null=False)  # p_date
    arch     = CharField(null=False)  # p_arch
    srpm     = TextField(null=False)  # p_srpm
    fullname = TextField(null=False)  # p_fullname
    update   = IntegerField(default=0)  # p_update

    @classmethod
    def in_db(cls, tag_id, package, version, release, arch):
        """
        Returns whether or not this package exists in the database
        :param tag_id: integer of tag id to search in
        :param package: package name
        :param version: package version
        :param release: package release
        :param arch: package arch
        :return: boolean
        """
        if RPM_Package.select().where(
            (RPM_Package.tag_id == tag_id) &
            (RPM_Package.package == package) &
            (RPM_Package.version == version) &
            (RPM_Package.release == release) &
            (RPM_Package.arch == arch)
            ):
            return True
        return False


    def __repr__(self):
        return '<RPM Package {self.package}>'.format(self=self)


# the binary rpm provides index model
class RPM_ProvidesIndex(BaseModel):  # provides
    package_id     = IntegerField()  # p_record
    tag_id         = IntegerField()  # t_record
    providename_id = IntegerField()  # pv_record


# the binary rpm provides model
class RPM_ProvidesName(BaseModel):  # provides_names
    name = TextField(null=False)  # pv_name

    @classmethod
    def get_id(cls, name):
        """
        Returns the provides id for the provided provides name
        :param name: the name to lookup
        :return: int
        """
        pid = RPM_ProvidesName.get(RPM_ProvidesName.name == name)
        return pid.id

    def __repr__(self):
        return '<RPM ProvidesName {self.name}>'.format(self=self)


# the binary rpm requires index model
class RPM_RequiresIndex(BaseModel):  # requires
    package_id     = IntegerField()  # p_record
    tag_id         = IntegerField()  # t_record
    requirename_id = IntegerField()  # rq_record


# the binary rpm requires model
class RPM_RequiresName(BaseModel):  # requires_names
    name = TextField(null=False)  # rq_name

    @classmethod
    def get_id(cls, name):
        """
        Returns the requires id for the provided requires name
        :param name: the name to lookup
        :return: int
        """
        rid = RPM_RequiresName.get(RPM_RequiresName.name == name)
        return rid.id

    def __repr__(self):
        return '<RPM RequiresName {self.name}>'.format(self=self)


# the binary rpm symbols model
class RPM_Symbols(BaseModel):  # symbols
    package_id = IntegerField()  # p_record
    tag_id     = IntegerField()  # t_record
    file_id    = IntegerField()  # f_id
    symbols    = TextField(null=False)

    def __repr__(self):
        return '<RPM Symbol {self.symbols}>'.format(self=self)


# the binary rpm flags model
class RPM_Flags(BaseModel):  # flags
    package_id = IntegerField()  # p_record
    tag_id     = IntegerField()  # t_record
    file_id    = IntegerField()  # f_id
    relro      = IntegerField(default=0)  # f_relro
    ssp        = IntegerField(default=0)  # f_ssp
    pie        = IntegerField(default=0)  # f_pie
    fortify    = IntegerField(default=0)  # f_fortify
    nx         = IntegerField(default=0)  # f_nx

    @classmethod
    def get_named(cls, id):
        """
        Returns described flags rather than their numerical values we return what the values mean
        :param id: integer of flag id to look up
        :return: object
        """
        f = RPM_Flags.get(RPM_Flags.id == id)

        # these are the default values
        newflags = namedtuple('newflags', 'relro ssp nx pie fortify')
        flag = newflags(relro='none', ssp='not found', nx='disabled', pie='none', fortify='not found')

        if f.relro == 1:
            flag.relro = 'full'
        elif f.relro == 2:
            flag.relro = 'partial'

        if f.ssp == 1:
            flag.ssp = 'found'

        if f.nx == 1:
            flag.nx = 'enabled'

        if f.pie == 2:
            flag.pie = 'DSO'
        elif f.pie == 1:
            flag.pie = 'enabled'

        if f.fortify == 1:
            flag.fortify = 'found'

        return flag

# the binary rpm tag model
class RPM_Tag(BaseModel):  # tags
    tag         = CharField(null=False)
    path        = CharField(null=False)
    tdate       = CharField(null=False)
    update_path = CharField(null=False)
    update_date = CharField(null=False)

    @classmethod
    def get_tag(cls, id):
        """
        Returns the tag name when provided the tag id
        :param id: integer of tag id to look up
        :return: string
        """
        t = RPM_Tag.get(RPM_Tag.id == id)
        return t.tag

    def __repr__(self):
        return '<RPM Tag {self.tag}>'.format(self=self)


# the binary alreadyseen model
class RPM_AlreadySeen(BaseModel):
    fullname = TextField(null=False)
    tag_id   = IntegerField()  # t_record