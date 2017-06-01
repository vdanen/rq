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

    @classmethod
    def get_id(cls, name):
        """
        Returns the tag id for the provided tag name
        :param name: the name to lookup
        :return: int
        """
        tid = RPM_Tag.get(RPM_Tag.tag == name)
        return tid.id

    @classmethod
    def get_list(cls):
        """
        Returns a list of tags
        :return: list
        """
        return RPM_Tag.select().order_by(RPM_Tag.tag)

    @classmethod
    def info(cls, tag):
        """
        Return information on this tag
        :return: dict (id, path) or False
        """
        t = RPM_Tag.get(RPM_Tag.tag == tag)
        if t:
            return {'id': t.id, 'path': t.path}
        else:
            return False

    @classmethod
    def exists(cls, tag):
        """
        Return True if this tag exists, False otherwise
        :param tag: tag name to lookup
        :return: bool
        """
        t = RPM_Tag.select().where(RPM_Tag.tag == tag).limit(1)
        if t:
            return True
        return False

    @property
    def package_count(self):
        """
        Return the number of packages
        :return: int
        """
        return RPM_Package.select().where(RPM_Package.tag_id == self.id).count()

    @property
    def update_count(self):
        """
        Return the number of updates packages
        :return: int
        """
        return RPM_Package.select().where((RPM_Package.tag_id == self.id) & (RPM_Package.update == 1)).count()


    def __repr__(self):
        return '<RPM Tag {self.tag}>'.format(self=self)


# the binary rpm package model
class RPM_Package(BaseModel):
    tag_id = ForeignKeyField(RPM_Tag, related_name='package')  # t_record
    # IntegerField()  # t_record
    tag = TextField(null=False)  # p_tag
    package = TextField(null=False)  # p_package
    version = TextField(null=False)  # p_version
    release = TextField(null=False)  # p_release
    date = TextField(null=False)  # p_date
    arch = CharField(null=False)  # p_arch
    srpm = TextField(null=False)  # p_srpm
    fullname = TextField(null=False)  # p_fullname
    update = IntegerField(default=0)  # p_update

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
        if RPM_Package.select().where((RPM_Package.tag_id == tag_id) &
                                    (RPM_Package.package == package) &
                                    (RPM_Package.version == version) &
                                    (RPM_Package.release == release) &
                                    (RPM_Package.arch == arch)
        ):
            return True
        return False

    @classmethod
    def list_updates(cls, tag):
        """
        Returns a list of packages for which an update exists
        :param tag: the named tag
        :return: list
        """
        t = RPM_Tag.get(RPM_Tag.tag == tag)
        return RPM_Package.select(RPM_Package.fullname).where(
            (RPM_Package.tag_id == t.id) & (RPM_Package.update == 1)).order_by(RPM_Package.fullname.asc())

    @classmethod
    def delete_tags(cls, tag_id):
        """
        Delete packages with this tag_id
        :param tag_id: tag_id to remove
        :return: int (number of packages removed)
        """
        query   = RPM_Package.delete().where(RPM_Package.tag_id == tag_id)
        removed = query.execute()
        return removed

    def __repr__(self):
        return '<RPM Package {self.package}>'.format(self=self)


# the binary rpm provides index model
class RPM_ProvidesIndex(BaseModel):  # provides
    package_id = ForeignKeyField(RPM_Package, related_name='provides')  # p_record
    # IntegerField()  # p_record
    tag_id = ForeignKeyField(RPM_Tag, related_name='provides')  # t_record
    # IntegerField()  # t_record
    providename_id = IntegerField()  # pv_record

    @classmethod
    def delete_tags(cls, tag_id):
        """
        Delete provides with this tag_id
        :param tag_id: tag_id to remove
        :return: int (number of provides entries removed)
        """
        query   = RPM_ProvidesIndex.delete().where(RPM_ProvidesIndex.tag_id == tag_id)
        removed = query.execute()
        return removed


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
    package_id = ForeignKeyField(RPM_Package, related_name='requires')  # p_record
    # IntegerField()  # p_record
    tag_id = ForeignKeyField(RPM_Tag, related_name='requires')  # t_record
    # IntegerField()  # t_record
    requirename_id = IntegerField()  # rq_record

    @classmethod
    def delete_tags(cls, tag_id):
        """
        Delete requires with this tag_id
        :param tag_id: tag_id to remove
        :return: int (number of requires entries removed)
        """
        query   = RPM_RequiresIndex.delete().where(RPM_RequiresIndex.tag_id == tag_id)
        removed = query.execute()
        return removed


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


# the binary rpm files model
class RPM_File(BaseModel):
    package_id = ForeignKeyField(RPM_Package, related_name='file')  # p_record
    # IntegerField()  # p_record
    tag_id = ForeignKeyField(RPM_Tag, related_name='file')  # t_record
    # IntegerField()  # t_record
    user_id = ForeignKeyField(RPM_User, related_name='file')  # u_record
    # IntegerField()  # u_record
    group_id = ForeignKeyField(RPM_Group, related_name='file')  # g_record
    # IntegerField()  # g_record
    file = TextField()  # files
    is_suid = IntegerField(default=0)  # f_is_suid
    is_sgid = IntegerField(default=0)  # f_is_sgid
    perms = CharField()  # f_perms

    @classmethod
    def get_id(cls, file, tag_id, package_id):
        """
        Returns the file id for the provided file name, package record and tag record
        :param file: the file to lookup
        :param tag_id: the tag id to lookup
        :param package_id: the package id to lookup
        :return: int
        """
        file = RPM_File.get(
            (RPM_File.file == file) & (RPM_File.package_id == package_id) & (RPM_File.tag_id == tag_id))
        return file.id

    @classmethod
    def get_sxid(cls, tag_id, db_col):
        """
        Function to return a list of files that are either suid or sgid, per tag
        :param tag_id: the tag id to reference
        :param db_col: the database column to use (either is_suid or is_sgid)
        :return: list
        """
        if db_col == 'is_suid':
            query = (
            RPM_File.select(RPM_File, RPM_Package, RPM_User, RPM_Group).join(RPM_User).join(RPM_Group).join(
                RPM_Package).where((RPM_File.is_suid == 1) & (RPM_File.tag_id == tag_id)).order_by(
                RPM_Package.package.asc()))
        elif db_col == 'is_sgid':
            query = (
            RPM_File.select(RPM_File, RPM_Package, RPM_User, RPM_Group).join(RPM_User).join(RPM_Group).join(
                RPM_Package).where((RPM_File.is_sgid == 1) & (RPM_File.tag_id == tag_id)).order_by(
                RPM_Package.package.asc()))

        return query
        # TODO return RPM_File.select().where((Entry.published == True) & (Entry.type == 'page') & (Entry.timestamp <= now)).order_by(Entry.timestamp.desc()).limit(numdisplay)

        # query = "SELECT p_package, files, f_user, f_group, f_perms FROM files JOIN packages ON \
        # (files.p_record = packages.p_record) LEFT JOIN user_names ON (files.u_record = user_names.u_record) \
        # LEFT JOIN group_names ON (files.g_record = group_names.g_record) WHERE %s = 1 AND files.t_record = %s \
        # ORDER BY p_package ASC" % (db_col, tag_id)
        # results = self.db.fetch_all(query)

    @classmethod
    def delete_tags(cls, tag_id):
        """
        Delete files with this tag_id
        :param tag_id: tag_id to remove
        :return: int (number of files removed)
        """
        query   = RPM_File.delete().where(RPM_File.tag_id == tag_id)
        removed = query.execute()
        return removed


    def __repr__(self):
        return '<RPM File {self.file}>'.format(self=self)


# the binary rpm symbols model
class RPM_Symbols(BaseModel):  # symbols
    package_id = ForeignKeyField(RPM_Package, related_name='symbols') # p_record
    #IntegerField()  # p_record
    tag_id     = ForeignKeyField(RPM_Tag, related_name='symbols') # t_record
    #IntegerField()  # t_record
    file_id    = ForeignKeyField(RPM_File, related_name='symbols') # f_id
    #IntegerField()  # f_id
    symbols    = TextField(null=False)

    @classmethod
    def delete_tags(cls, tag_id):
        """
        Delete symbols with this tag_id
        :param tag_id: tag_id to remove
        :return: int (number of symbols removed)
        """
        query   = RPM_Symbols.delete().where(RPM_Symbols.tag_id == tag_id)
        removed = query.execute()
        return removed

    def __repr__(self):
        return '<RPM Symbol {self.symbols}>'.format(self=self)


# the binary rpm flags model
class RPM_Flags(BaseModel):  # flags
    package_id = ForeignKeyField(RPM_Package, related_name='flags')  # p_record
    # IntegerField()  # p_record
    tag_id = ForeignKeyField(RPM_Tag, related_name='flags')  # t_record
    # IntegerField()  # t_record
    file_id = ForeignKeyField(RPM_File, related_name='flags')  # f_id
    # IntegerField()  # f_id
    relro = IntegerField(default=0)  # f_relro
    ssp = IntegerField(default=0)  # f_ssp
    pie = IntegerField(default=0)  # f_pie
    fortify = IntegerField(default=0)  # f_fortify
    nx = IntegerField(default=0)  # f_nx

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

    @classmethod
    def delete_tags(cls, tag_id):
        """
        Delete flags with this tag_id
        :param tag_id: tag_id to remove
        :return: int (number of flag entries removed)
        """
        query   = RPM_Flags.delete().where(RPM_Flags.tag_id == tag_id)
        removed = query.execute()
        return removed



# the binary alreadyseen model
class RPM_AlreadySeen(BaseModel):
    fullname = TextField(null=False)
    tag_id = ForeignKeyField(RPM_Tag, related_name='alreadyseen')
    # IntegerField()  # t_record

    @classmethod
    def delete_tags(cls, tag_id):
        """
        Delete alreadyseen items with this tag_id
        :param tag_id: tag_id to remove
        :return: int (number of alreadyseen entries removed)
        """
        query   = RPM_AlreadySeen.delete().where(RPM_AlreadySeen.tag_id == tag_id)
        removed = query.execute()
        return removed
