import type { Schema, Attribute } from '@strapi/strapi';

export interface AdminPermission extends Schema.CollectionType {
  collectionName: 'admin_permissions';
  info: {
    name: 'Permission';
    description: '';
    singularName: 'permission';
    pluralName: 'permissions';
    displayName: 'Permission';
  };
  pluginOptions: {
    'content-manager': {
      visible: false;
    };
    'content-type-builder': {
      visible: false;
    };
  };
  attributes: {
    action: Attribute.String &
      Attribute.Required &
      Attribute.SetMinMaxLength<{
        minLength: 1;
      }>;
    actionParameters: Attribute.JSON & Attribute.DefaultTo<{}>;
    subject: Attribute.String &
      Attribute.SetMinMaxLength<{
        minLength: 1;
      }>;
    properties: Attribute.JSON & Attribute.DefaultTo<{}>;
    conditions: Attribute.JSON & Attribute.DefaultTo<[]>;
    role: Attribute.Relation<'admin::permission', 'manyToOne', 'admin::role'>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'admin::permission',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'admin::permission',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
  };
}

export interface AdminUser extends Schema.CollectionType {
  collectionName: 'admin_users';
  info: {
    name: 'User';
    description: '';
    singularName: 'user';
    pluralName: 'users';
    displayName: 'User';
  };
  pluginOptions: {
    'content-manager': {
      visible: false;
    };
    'content-type-builder': {
      visible: false;
    };
  };
  attributes: {
    firstname: Attribute.String &
      Attribute.SetMinMaxLength<{
        minLength: 1;
      }>;
    lastname: Attribute.String &
      Attribute.SetMinMaxLength<{
        minLength: 1;
      }>;
    username: Attribute.String;
    email: Attribute.Email &
      Attribute.Required &
      Attribute.Private &
      Attribute.Unique &
      Attribute.SetMinMaxLength<{
        minLength: 6;
      }>;
    password: Attribute.Password &
      Attribute.Private &
      Attribute.SetMinMaxLength<{
        minLength: 6;
      }>;
    resetPasswordToken: Attribute.String & Attribute.Private;
    registrationToken: Attribute.String & Attribute.Private;
    isActive: Attribute.Boolean &
      Attribute.Private &
      Attribute.DefaultTo<false>;
    roles: Attribute.Relation<'admin::user', 'manyToMany', 'admin::role'> &
      Attribute.Private;
    blocked: Attribute.Boolean & Attribute.Private & Attribute.DefaultTo<false>;
    preferedLanguage: Attribute.String;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<'admin::user', 'oneToOne', 'admin::user'> &
      Attribute.Private;
    updatedBy: Attribute.Relation<'admin::user', 'oneToOne', 'admin::user'> &
      Attribute.Private;
  };
}

export interface AdminRole extends Schema.CollectionType {
  collectionName: 'admin_roles';
  info: {
    name: 'Role';
    description: '';
    singularName: 'role';
    pluralName: 'roles';
    displayName: 'Role';
  };
  pluginOptions: {
    'content-manager': {
      visible: false;
    };
    'content-type-builder': {
      visible: false;
    };
  };
  attributes: {
    name: Attribute.String &
      Attribute.Required &
      Attribute.Unique &
      Attribute.SetMinMaxLength<{
        minLength: 1;
      }>;
    code: Attribute.String &
      Attribute.Required &
      Attribute.Unique &
      Attribute.SetMinMaxLength<{
        minLength: 1;
      }>;
    description: Attribute.String;
    users: Attribute.Relation<'admin::role', 'manyToMany', 'admin::user'>;
    permissions: Attribute.Relation<
      'admin::role',
      'oneToMany',
      'admin::permission'
    >;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<'admin::role', 'oneToOne', 'admin::user'> &
      Attribute.Private;
    updatedBy: Attribute.Relation<'admin::role', 'oneToOne', 'admin::user'> &
      Attribute.Private;
  };
}

export interface AdminApiToken extends Schema.CollectionType {
  collectionName: 'strapi_api_tokens';
  info: {
    name: 'Api Token';
    singularName: 'api-token';
    pluralName: 'api-tokens';
    displayName: 'Api Token';
    description: '';
  };
  pluginOptions: {
    'content-manager': {
      visible: false;
    };
    'content-type-builder': {
      visible: false;
    };
  };
  attributes: {
    name: Attribute.String &
      Attribute.Required &
      Attribute.Unique &
      Attribute.SetMinMaxLength<{
        minLength: 1;
      }>;
    description: Attribute.String &
      Attribute.SetMinMaxLength<{
        minLength: 1;
      }> &
      Attribute.DefaultTo<''>;
    type: Attribute.Enumeration<['read-only', 'full-access', 'custom']> &
      Attribute.Required &
      Attribute.DefaultTo<'read-only'>;
    accessKey: Attribute.String &
      Attribute.Required &
      Attribute.SetMinMaxLength<{
        minLength: 1;
      }>;
    lastUsedAt: Attribute.DateTime;
    permissions: Attribute.Relation<
      'admin::api-token',
      'oneToMany',
      'admin::api-token-permission'
    >;
    expiresAt: Attribute.DateTime;
    lifespan: Attribute.BigInteger;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'admin::api-token',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'admin::api-token',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
  };
}

export interface AdminApiTokenPermission extends Schema.CollectionType {
  collectionName: 'strapi_api_token_permissions';
  info: {
    name: 'API Token Permission';
    description: '';
    singularName: 'api-token-permission';
    pluralName: 'api-token-permissions';
    displayName: 'API Token Permission';
  };
  pluginOptions: {
    'content-manager': {
      visible: false;
    };
    'content-type-builder': {
      visible: false;
    };
  };
  attributes: {
    action: Attribute.String &
      Attribute.Required &
      Attribute.SetMinMaxLength<{
        minLength: 1;
      }>;
    token: Attribute.Relation<
      'admin::api-token-permission',
      'manyToOne',
      'admin::api-token'
    >;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'admin::api-token-permission',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'admin::api-token-permission',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
  };
}

export interface AdminTransferToken extends Schema.CollectionType {
  collectionName: 'strapi_transfer_tokens';
  info: {
    name: 'Transfer Token';
    singularName: 'transfer-token';
    pluralName: 'transfer-tokens';
    displayName: 'Transfer Token';
    description: '';
  };
  pluginOptions: {
    'content-manager': {
      visible: false;
    };
    'content-type-builder': {
      visible: false;
    };
  };
  attributes: {
    name: Attribute.String &
      Attribute.Required &
      Attribute.Unique &
      Attribute.SetMinMaxLength<{
        minLength: 1;
      }>;
    description: Attribute.String &
      Attribute.SetMinMaxLength<{
        minLength: 1;
      }> &
      Attribute.DefaultTo<''>;
    accessKey: Attribute.String &
      Attribute.Required &
      Attribute.SetMinMaxLength<{
        minLength: 1;
      }>;
    lastUsedAt: Attribute.DateTime;
    permissions: Attribute.Relation<
      'admin::transfer-token',
      'oneToMany',
      'admin::transfer-token-permission'
    >;
    expiresAt: Attribute.DateTime;
    lifespan: Attribute.BigInteger;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'admin::transfer-token',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'admin::transfer-token',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
  };
}

export interface AdminTransferTokenPermission extends Schema.CollectionType {
  collectionName: 'strapi_transfer_token_permissions';
  info: {
    name: 'Transfer Token Permission';
    description: '';
    singularName: 'transfer-token-permission';
    pluralName: 'transfer-token-permissions';
    displayName: 'Transfer Token Permission';
  };
  pluginOptions: {
    'content-manager': {
      visible: false;
    };
    'content-type-builder': {
      visible: false;
    };
  };
  attributes: {
    action: Attribute.String &
      Attribute.Required &
      Attribute.SetMinMaxLength<{
        minLength: 1;
      }>;
    token: Attribute.Relation<
      'admin::transfer-token-permission',
      'manyToOne',
      'admin::transfer-token'
    >;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'admin::transfer-token-permission',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'admin::transfer-token-permission',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
  };
}

export interface PluginUploadFile extends Schema.CollectionType {
  collectionName: 'files';
  info: {
    singularName: 'file';
    pluralName: 'files';
    displayName: 'File';
    description: '';
  };
  pluginOptions: {
    'content-manager': {
      visible: false;
    };
    'content-type-builder': {
      visible: false;
    };
  };
  attributes: {
    name: Attribute.String & Attribute.Required;
    alternativeText: Attribute.String;
    caption: Attribute.String;
    width: Attribute.Integer;
    height: Attribute.Integer;
    formats: Attribute.JSON;
    hash: Attribute.String & Attribute.Required;
    ext: Attribute.String;
    mime: Attribute.String & Attribute.Required;
    size: Attribute.Decimal & Attribute.Required;
    url: Attribute.String & Attribute.Required;
    previewUrl: Attribute.String;
    provider: Attribute.String & Attribute.Required;
    provider_metadata: Attribute.JSON;
    related: Attribute.Relation<'plugin::upload.file', 'morphToMany'>;
    folder: Attribute.Relation<
      'plugin::upload.file',
      'manyToOne',
      'plugin::upload.folder'
    > &
      Attribute.Private;
    folderPath: Attribute.String &
      Attribute.Required &
      Attribute.Private &
      Attribute.SetMinMax<{
        min: 1;
      }>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'plugin::upload.file',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'plugin::upload.file',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
  };
}

export interface PluginUploadFolder extends Schema.CollectionType {
  collectionName: 'upload_folders';
  info: {
    singularName: 'folder';
    pluralName: 'folders';
    displayName: 'Folder';
  };
  pluginOptions: {
    'content-manager': {
      visible: false;
    };
    'content-type-builder': {
      visible: false;
    };
  };
  attributes: {
    name: Attribute.String &
      Attribute.Required &
      Attribute.SetMinMax<{
        min: 1;
      }>;
    pathId: Attribute.Integer & Attribute.Required & Attribute.Unique;
    parent: Attribute.Relation<
      'plugin::upload.folder',
      'manyToOne',
      'plugin::upload.folder'
    >;
    children: Attribute.Relation<
      'plugin::upload.folder',
      'oneToMany',
      'plugin::upload.folder'
    >;
    files: Attribute.Relation<
      'plugin::upload.folder',
      'oneToMany',
      'plugin::upload.file'
    >;
    path: Attribute.String &
      Attribute.Required &
      Attribute.SetMinMax<{
        min: 1;
      }>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'plugin::upload.folder',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'plugin::upload.folder',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
  };
}

export interface PluginI18NLocale extends Schema.CollectionType {
  collectionName: 'i18n_locale';
  info: {
    singularName: 'locale';
    pluralName: 'locales';
    collectionName: 'locales';
    displayName: 'Locale';
    description: '';
  };
  options: {
    draftAndPublish: false;
  };
  pluginOptions: {
    'content-manager': {
      visible: false;
    };
    'content-type-builder': {
      visible: false;
    };
  };
  attributes: {
    name: Attribute.String &
      Attribute.SetMinMax<{
        min: 1;
        max: 50;
      }>;
    code: Attribute.String & Attribute.Unique;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'plugin::i18n.locale',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'plugin::i18n.locale',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
  };
}

export interface PluginUsersPermissionsPermission
  extends Schema.CollectionType {
  collectionName: 'up_permissions';
  info: {
    name: 'permission';
    description: '';
    singularName: 'permission';
    pluralName: 'permissions';
    displayName: 'Permission';
  };
  pluginOptions: {
    'content-manager': {
      visible: false;
    };
    'content-type-builder': {
      visible: false;
    };
  };
  attributes: {
    action: Attribute.String & Attribute.Required;
    role: Attribute.Relation<
      'plugin::users-permissions.permission',
      'manyToOne',
      'plugin::users-permissions.role'
    >;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'plugin::users-permissions.permission',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'plugin::users-permissions.permission',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
  };
}

export interface PluginUsersPermissionsRole extends Schema.CollectionType {
  collectionName: 'up_roles';
  info: {
    name: 'role';
    description: '';
    singularName: 'role';
    pluralName: 'roles';
    displayName: 'Role';
  };
  pluginOptions: {
    'content-manager': {
      visible: false;
    };
    'content-type-builder': {
      visible: false;
    };
  };
  attributes: {
    name: Attribute.String &
      Attribute.Required &
      Attribute.SetMinMaxLength<{
        minLength: 3;
      }>;
    description: Attribute.String;
    type: Attribute.String & Attribute.Unique;
    permissions: Attribute.Relation<
      'plugin::users-permissions.role',
      'oneToMany',
      'plugin::users-permissions.permission'
    >;
    users: Attribute.Relation<
      'plugin::users-permissions.role',
      'oneToMany',
      'plugin::users-permissions.user'
    >;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'plugin::users-permissions.role',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'plugin::users-permissions.role',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
  };
}

export interface PluginUsersPermissionsUser extends Schema.CollectionType {
  collectionName: 'up_users';
  info: {
    name: 'user';
    description: '';
    singularName: 'user';
    pluralName: 'users';
    displayName: 'User';
  };
  options: {
    draftAndPublish: false;
    timestamps: true;
  };
  attributes: {
    username: Attribute.String &
      Attribute.Required &
      Attribute.Unique &
      Attribute.SetMinMaxLength<{
        minLength: 3;
      }>;
    email: Attribute.Email &
      Attribute.Required &
      Attribute.SetMinMaxLength<{
        minLength: 6;
      }>;
    provider: Attribute.String;
    password: Attribute.Password &
      Attribute.Private &
      Attribute.SetMinMaxLength<{
        minLength: 6;
      }>;
    resetPasswordToken: Attribute.String & Attribute.Private;
    confirmationToken: Attribute.String & Attribute.Private;
    confirmed: Attribute.Boolean & Attribute.DefaultTo<false>;
    blocked: Attribute.Boolean & Attribute.DefaultTo<false>;
    role: Attribute.Relation<
      'plugin::users-permissions.user',
      'manyToOne',
      'plugin::users-permissions.role'
    >;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'plugin::users-permissions.user',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'plugin::users-permissions.user',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
  };
}

export interface ApiContactDetailContactDetail extends Schema.SingleType {
  collectionName: 'contact_details';
  info: {
    singularName: 'contact-detail';
    pluralName: 'contact-details';
    displayName: 'Contact Details';
    description: '';
  };
  options: {
    draftAndPublish: true;
  };
  pluginOptions: {
    i18n: {
      localized: true;
    };
  };
  attributes: {
    name: Attribute.String &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    address: Attribute.String &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    phone: Attribute.String &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    email: Attribute.String &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    registration: Attribute.String &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    publishedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::contact-detail.contact-detail',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::contact-detail.contact-detail',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    localizations: Attribute.Relation<
      'api::contact-detail.contact-detail',
      'oneToMany',
      'api::contact-detail.contact-detail'
    >;
    locale: Attribute.String;
  };
}

export interface ApiDataInfoDataInfo extends Schema.CollectionType {
  collectionName: 'data_infos';
  info: {
    singularName: 'data-info';
    pluralName: 'data-infos';
    displayName: 'Data Info';
    description: '';
  };
  options: {
    draftAndPublish: false;
  };
  pluginOptions: {
    i18n: {
      localized: true;
    };
  };
  attributes: {
    slug: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    content: Attribute.Text &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    data_sources: Attribute.Relation<
      'api::data-info.data-info',
      'oneToMany',
      'api::data-source.data-source'
    >;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::data-info.data-info',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::data-info.data-info',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    localizations: Attribute.Relation<
      'api::data-info.data-info',
      'oneToMany',
      'api::data-info.data-info'
    >;
    locale: Attribute.String;
  };
}

export interface ApiDataSourceDataSource extends Schema.CollectionType {
  collectionName: 'data_sources';
  info: {
    singularName: 'data-source';
    pluralName: 'data-sources';
    displayName: 'Data Source';
    description: '';
  };
  options: {
    draftAndPublish: false;
  };
  pluginOptions: {
    i18n: {
      localized: true;
    };
  };
  attributes: {
    slug: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    title: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    url: Attribute.String &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::data-source.data-source',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::data-source.data-source',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    localizations: Attribute.Relation<
      'api::data-source.data-source',
      'oneToMany',
      'api::data-source.data-source'
    >;
    locale: Attribute.String;
  };
}

export interface ApiDataToolDataTool extends Schema.CollectionType {
  collectionName: 'data_tools';
  info: {
    singularName: 'data-tool';
    pluralName: 'data-tools';
    displayName: 'Data Tool';
    description: '';
  };
  options: {
    draftAndPublish: true;
  };
  pluginOptions: {
    i18n: {
      localized: true;
    };
  };
  attributes: {
    name: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    description: Attribute.Text &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    site: Attribute.String &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    languages: Attribute.Relation<
      'api::data-tool.data-tool',
      'oneToMany',
      'api::data-tool-language.data-tool-language'
    >;
    data_tool_resource_types: Attribute.Relation<
      'api::data-tool.data-tool',
      'oneToMany',
      'api::data-tool-resource-type.data-tool-resource-type'
    >;
    geography: Attribute.Text &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    data_tool_ecosystems: Attribute.Relation<
      'api::data-tool.data-tool',
      'oneToMany',
      'api::data-tool-ecosystem.data-tool-ecosystem'
    >;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    publishedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::data-tool.data-tool',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::data-tool.data-tool',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    localizations: Attribute.Relation<
      'api::data-tool.data-tool',
      'oneToMany',
      'api::data-tool.data-tool'
    >;
    locale: Attribute.String;
  };
}

export interface ApiDataToolEcosystemDataToolEcosystem
  extends Schema.CollectionType {
  collectionName: 'data_tool_ecosystems';
  info: {
    singularName: 'data-tool-ecosystem';
    pluralName: 'data-tool-ecosystems';
    displayName: 'Data Tool Ecosystem';
    description: '';
  };
  options: {
    draftAndPublish: true;
  };
  pluginOptions: {
    i18n: {
      localized: true;
    };
  };
  attributes: {
    name: Attribute.String &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    publishedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::data-tool-ecosystem.data-tool-ecosystem',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::data-tool-ecosystem.data-tool-ecosystem',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    localizations: Attribute.Relation<
      'api::data-tool-ecosystem.data-tool-ecosystem',
      'oneToMany',
      'api::data-tool-ecosystem.data-tool-ecosystem'
    >;
    locale: Attribute.String;
  };
}

export interface ApiDataToolLanguageDataToolLanguage
  extends Schema.CollectionType {
  collectionName: 'data_tool_languages';
  info: {
    singularName: 'data-tool-language';
    pluralName: 'data-tool-languages';
    displayName: 'Data Tool Language';
    description: '';
  };
  options: {
    draftAndPublish: true;
  };
  pluginOptions: {
    i18n: {
      localized: true;
    };
  };
  attributes: {
    name: Attribute.String &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    slug: Attribute.String &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    data_tool: Attribute.Relation<
      'api::data-tool-language.data-tool-language',
      'manyToOne',
      'api::data-tool.data-tool'
    >;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    publishedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::data-tool-language.data-tool-language',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::data-tool-language.data-tool-language',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    localizations: Attribute.Relation<
      'api::data-tool-language.data-tool-language',
      'oneToMany',
      'api::data-tool-language.data-tool-language'
    >;
    locale: Attribute.String;
  };
}

export interface ApiDataToolResourceTypeDataToolResourceType
  extends Schema.CollectionType {
  collectionName: 'data_tool_resource_types';
  info: {
    singularName: 'data-tool-resource-type';
    pluralName: 'data-tool-resource-types';
    displayName: 'Data Tool Resource Type';
    description: '';
  };
  options: {
    draftAndPublish: true;
  };
  pluginOptions: {
    i18n: {
      localized: true;
    };
  };
  attributes: {
    name: Attribute.String &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    publishedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::data-tool-resource-type.data-tool-resource-type',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::data-tool-resource-type.data-tool-resource-type',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    localizations: Attribute.Relation<
      'api::data-tool-resource-type.data-tool-resource-type',
      'oneToMany',
      'api::data-tool-resource-type.data-tool-resource-type'
    >;
    locale: Attribute.String;
  };
}

export interface ApiDatasetDataset extends Schema.CollectionType {
  collectionName: 'datasets';
  info: {
    singularName: 'dataset';
    pluralName: 'datasets';
    displayName: 'Dataset';
    description: '';
  };
  options: {
    draftAndPublish: true;
  };
  pluginOptions: {
    i18n: {
      localized: true;
    };
  };
  attributes: {
    name: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    layers: Attribute.Relation<
      'api::dataset.dataset',
      'oneToMany',
      'api::layer.layer'
    >;
    slug: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    publishedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::dataset.dataset',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::dataset.dataset',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    localizations: Attribute.Relation<
      'api::dataset.dataset',
      'oneToMany',
      'api::dataset.dataset'
    >;
    locale: Attribute.String;
  };
}

export interface ApiEnvironmentEnvironment extends Schema.CollectionType {
  collectionName: 'environments';
  info: {
    singularName: 'environment';
    pluralName: 'environments';
    displayName: 'Environment';
    description: '';
  };
  options: {
    draftAndPublish: false;
  };
  pluginOptions: {
    i18n: {
      localized: true;
    };
  };
  attributes: {
    name: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    slug: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::environment.environment',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::environment.environment',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    localizations: Attribute.Relation<
      'api::environment.environment',
      'oneToMany',
      'api::environment.environment'
    >;
    locale: Attribute.String;
  };
}

export interface ApiFeatureFlagFeatureFlag extends Schema.CollectionType {
  collectionName: 'feature_flags';
  info: {
    singularName: 'feature-flag';
    pluralName: 'feature-flags';
    displayName: 'Feature Flags';
  };
  options: {
    draftAndPublish: true;
  };
  attributes: {
    feature: Attribute.String & Attribute.Required & Attribute.Unique;
    description: Attribute.Text;
    payload: Attribute.JSON;
    active_on: Attribute.DateTime;
    archived: Attribute.Boolean & Attribute.DefaultTo<false>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    publishedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::feature-flag.feature-flag',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::feature-flag.feature-flag',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
  };
}

export interface ApiFishingProtectionLevelFishingProtectionLevel
  extends Schema.CollectionType {
  collectionName: 'fishing_protection_levels';
  info: {
    singularName: 'fishing-protection-level';
    pluralName: 'fishing-protection-levels';
    displayName: 'Fishing Protection Level';
    description: '';
  };
  options: {
    draftAndPublish: false;
  };
  pluginOptions: {
    i18n: {
      localized: true;
    };
  };
  attributes: {
    slug: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    name: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    info: Attribute.Text &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::fishing-protection-level.fishing-protection-level',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::fishing-protection-level.fishing-protection-level',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    localizations: Attribute.Relation<
      'api::fishing-protection-level.fishing-protection-level',
      'oneToMany',
      'api::fishing-protection-level.fishing-protection-level'
    >;
    locale: Attribute.String;
  };
}

export interface ApiFishingProtectionLevelStatFishingProtectionLevelStat
  extends Schema.CollectionType {
  collectionName: 'fishing_protection_level_stats';
  info: {
    singularName: 'fishing-protection-level-stat';
    pluralName: 'fishing-protection-level-stats';
    displayName: 'Fishing Protection Level Stats';
    description: 'Calculation of area of protection by location and fishing protection level';
  };
  options: {
    draftAndPublish: false;
  };
  attributes: {
    location: Attribute.Relation<
      'api::fishing-protection-level-stat.fishing-protection-level-stat',
      'manyToOne',
      'api::location.location'
    >;
    fishing_protection_level: Attribute.Relation<
      'api::fishing-protection-level-stat.fishing-protection-level-stat',
      'oneToOne',
      'api::fishing-protection-level.fishing-protection-level'
    >;
    area: Attribute.Decimal &
      Attribute.Required &
      Attribute.SetMinMax<{
        min: 0;
      }>;
    pct: Attribute.Float;
    total_area: Attribute.BigInteger;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::fishing-protection-level-stat.fishing-protection-level-stat',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::fishing-protection-level-stat.fishing-protection-level-stat',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
  };
}

export interface ApiHabitatHabitat extends Schema.CollectionType {
  collectionName: 'habitats';
  info: {
    singularName: 'habitat';
    pluralName: 'habitats';
    displayName: 'Habitat';
    description: '';
  };
  options: {
    draftAndPublish: false;
  };
  pluginOptions: {
    i18n: {
      localized: true;
    };
  };
  attributes: {
    slug: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    name: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    info: Attribute.Text &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::habitat.habitat',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::habitat.habitat',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    localizations: Attribute.Relation<
      'api::habitat.habitat',
      'oneToMany',
      'api::habitat.habitat'
    >;
    locale: Attribute.String;
  };
}

export interface ApiHabitatStatHabitatStat extends Schema.CollectionType {
  collectionName: 'habitat_stats';
  info: {
    singularName: 'habitat-stat';
    pluralName: 'habitat-stats';
    displayName: 'Habitat Stats';
    description: 'Calculation of area of protection by location, habitat and year';
  };
  options: {
    draftAndPublish: false;
  };
  attributes: {
    location: Attribute.Relation<
      'api::habitat-stat.habitat-stat',
      'oneToOne',
      'api::location.location'
    >;
    habitat: Attribute.Relation<
      'api::habitat-stat.habitat-stat',
      'oneToOne',
      'api::habitat.habitat'
    >;
    year: Attribute.Integer & Attribute.Required;
    protected_area: Attribute.Decimal &
      Attribute.Required &
      Attribute.SetMinMax<{
        min: 0;
      }>;
    total_area: Attribute.Decimal &
      Attribute.Required &
      Attribute.SetMinMax<{
        min: 0;
      }>;
    environment: Attribute.Relation<
      'api::habitat-stat.habitat-stat',
      'oneToOne',
      'api::environment.environment'
    >;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::habitat-stat.habitat-stat',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::habitat-stat.habitat-stat',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
  };
}

export interface ApiLayerLayer extends Schema.CollectionType {
  collectionName: 'layers';
  info: {
    singularName: 'layer';
    pluralName: 'layers';
    displayName: 'Layer';
    description: '';
  };
  options: {
    draftAndPublish: true;
  };
  pluginOptions: {
    i18n: {
      localized: true;
    };
  };
  attributes: {
    title: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    type: Attribute.Enumeration<['mapbox', 'deckgl', 'carto']> &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    config: Attribute.JSON &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    params_config: Attribute.JSON &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    interaction_config: Attribute.JSON &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    metadata: Attribute.Component<'documentation.metadata'> &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    dataset: Attribute.Relation<
      'api::layer.layer',
      'oneToOne',
      'api::dataset.dataset'
    >;
    legend_config: Attribute.Component<'legend.legend'> &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    default: Attribute.Boolean &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }> &
      Attribute.DefaultTo<false>;
    environment: Attribute.Relation<
      'api::layer.layer',
      'oneToOne',
      'api::environment.environment'
    >;
    slug: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    publishedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::layer.layer',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::layer.layer',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    localizations: Attribute.Relation<
      'api::layer.layer',
      'oneToMany',
      'api::layer.layer'
    >;
    locale: Attribute.String;
  };
}

export interface ApiLocationLocation extends Schema.CollectionType {
  collectionName: 'locations';
  info: {
    singularName: 'location';
    pluralName: 'locations';
    displayName: 'Location';
    description: 'Stores names of geographical locations of different types (worldwide, country, region).';
  };
  options: {
    draftAndPublish: false;
  };
  attributes: {
    code: Attribute.String & Attribute.Required;
    name: Attribute.String & Attribute.Required;
    total_marine_area: Attribute.BigInteger & Attribute.Required;
    type: Attribute.String & Attribute.Required;
    groups: Attribute.Relation<
      'api::location.location',
      'manyToMany',
      'api::location.location'
    >;
    members: Attribute.Relation<
      'api::location.location',
      'manyToMany',
      'api::location.location'
    >;
    fishing_protection_level_stats: Attribute.Relation<
      'api::location.location',
      'oneToMany',
      'api::fishing-protection-level-stat.fishing-protection-level-stat'
    >;
    mpaa_protection_level_stats: Attribute.Relation<
      'api::location.location',
      'oneToOne',
      'api::mpaa-protection-level-stat.mpaa-protection-level-stat'
    >;
    protection_coverage_stats: Attribute.Relation<
      'api::location.location',
      'oneToMany',
      'api::protection-coverage-stat.protection-coverage-stat'
    >;
    marine_bounds: Attribute.JSON;
    total_terrestrial_area: Attribute.BigInteger & Attribute.Required;
    terrestrial_bounds: Attribute.JSON;
    name_es: Attribute.String & Attribute.Required;
    name_fr: Attribute.String & Attribute.Required;
    marine_target: Attribute.Integer &
      Attribute.SetMinMax<{
        min: 0;
        max: 100;
      }>;
    marine_target_year: Attribute.Integer;
    pas: Attribute.Relation<
      'api::location.location',
      'oneToMany',
      'api::pa.pa'
    >;
    name_pt: Attribute.String & Attribute.Required;
    has_shared_marine_area: Attribute.Boolean;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::location.location',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::location.location',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
  };
}

export interface ApiMpaIucnCategoryMpaIucnCategory
  extends Schema.CollectionType {
  collectionName: 'mpa_iucn_categories';
  info: {
    singularName: 'mpa-iucn-category';
    pluralName: 'mpa-iucn-categories';
    displayName: 'MPA iucn category';
    description: '';
  };
  options: {
    draftAndPublish: false;
  };
  pluginOptions: {
    i18n: {
      localized: true;
    };
  };
  attributes: {
    slug: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    name: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    info: Attribute.Text &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::mpa-iucn-category.mpa-iucn-category',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::mpa-iucn-category.mpa-iucn-category',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    localizations: Attribute.Relation<
      'api::mpa-iucn-category.mpa-iucn-category',
      'oneToMany',
      'api::mpa-iucn-category.mpa-iucn-category'
    >;
    locale: Attribute.String;
  };
}

export interface ApiMpaaEstablishmentStageMpaaEstablishmentStage
  extends Schema.CollectionType {
  collectionName: 'mpaa_establishment_stages';
  info: {
    singularName: 'mpaa-establishment-stage';
    pluralName: 'mpaa-establishment-stages';
    displayName: 'MPAA Establishment Stage';
    description: '';
  };
  options: {
    draftAndPublish: false;
  };
  pluginOptions: {
    i18n: {
      localized: true;
    };
  };
  attributes: {
    slug: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    name: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    info: Attribute.Text &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::mpaa-establishment-stage.mpaa-establishment-stage',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::mpaa-establishment-stage.mpaa-establishment-stage',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    localizations: Attribute.Relation<
      'api::mpaa-establishment-stage.mpaa-establishment-stage',
      'oneToMany',
      'api::mpaa-establishment-stage.mpaa-establishment-stage'
    >;
    locale: Attribute.String;
  };
}

export interface ApiMpaaProtectionLevelMpaaProtectionLevel
  extends Schema.CollectionType {
  collectionName: 'mpaa_protection_levels';
  info: {
    singularName: 'mpaa-protection-level';
    pluralName: 'mpaa-protection-levels';
    displayName: 'MPAA Protection Level';
    description: '';
  };
  options: {
    draftAndPublish: false;
  };
  pluginOptions: {
    i18n: {
      localized: true;
    };
  };
  attributes: {
    slug: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    name: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    info: Attribute.Text &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::mpaa-protection-level.mpaa-protection-level',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::mpaa-protection-level.mpaa-protection-level',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    localizations: Attribute.Relation<
      'api::mpaa-protection-level.mpaa-protection-level',
      'oneToMany',
      'api::mpaa-protection-level.mpaa-protection-level'
    >;
    locale: Attribute.String;
  };
}

export interface ApiMpaaProtectionLevelStatMpaaProtectionLevelStat
  extends Schema.CollectionType {
  collectionName: 'mpaa_protection_level_stats';
  info: {
    singularName: 'mpaa-protection-level-stat';
    pluralName: 'mpaa-protection-level-stats';
    displayName: 'MPAA Protection Level Stats';
    description: '';
  };
  options: {
    draftAndPublish: false;
  };
  attributes: {
    mpaa_protection_level: Attribute.Relation<
      'api::mpaa-protection-level-stat.mpaa-protection-level-stat',
      'oneToOne',
      'api::mpaa-protection-level.mpaa-protection-level'
    >;
    area: Attribute.Decimal &
      Attribute.Required &
      Attribute.SetMinMax<{
        min: 0;
      }>;
    percentage: Attribute.Decimal;
    location: Attribute.Relation<
      'api::mpaa-protection-level-stat.mpaa-protection-level-stat',
      'oneToOne',
      'api::location.location'
    >;
    total_area: Attribute.BigInteger;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::mpaa-protection-level-stat.mpaa-protection-level-stat',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::mpaa-protection-level-stat.mpaa-protection-level-stat',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
  };
}

export interface ApiPaPa extends Schema.CollectionType {
  collectionName: 'pas';
  info: {
    singularName: 'pa';
    pluralName: 'pas';
    displayName: 'PA';
    description: '';
  };
  options: {
    draftAndPublish: false;
  };
  attributes: {
    name: Attribute.String & Attribute.Required;
    area: Attribute.Decimal &
      Attribute.Required &
      Attribute.SetMinMax<{
        min: 0;
      }>;
    year: Attribute.Integer &
      Attribute.SetMinMax<{
        min: 0;
      }>;
    protection_status: Attribute.Relation<
      'api::pa.pa',
      'oneToOne',
      'api::protection-status.protection-status'
    >;
    bbox: Attribute.JSON & Attribute.Required;
    children: Attribute.Relation<'api::pa.pa', 'oneToMany', 'api::pa.pa'>;
    data_source: Attribute.Relation<
      'api::pa.pa',
      'oneToOne',
      'api::data-source.data-source'
    >;
    mpaa_establishment_stage: Attribute.Relation<
      'api::pa.pa',
      'oneToOne',
      'api::mpaa-establishment-stage.mpaa-establishment-stage'
    >;
    location: Attribute.Relation<
      'api::pa.pa',
      'manyToOne',
      'api::location.location'
    >;
    wdpaid: Attribute.BigInteger;
    mpaa_protection_level: Attribute.Relation<
      'api::pa.pa',
      'oneToOne',
      'api::mpaa-protection-level.mpaa-protection-level'
    >;
    iucn_category: Attribute.Relation<
      'api::pa.pa',
      'oneToOne',
      'api::mpa-iucn-category.mpa-iucn-category'
    >;
    designation: Attribute.String;
    environment: Attribute.Relation<
      'api::pa.pa',
      'oneToOne',
      'api::environment.environment'
    >;
    coverage: Attribute.Decimal &
      Attribute.Required &
      Attribute.SetMinMax<{
        min: 0;
      }>;
    parent: Attribute.Relation<'api::pa.pa', 'oneToOne', 'api::pa.pa'>;
    zone_id: Attribute.BigInteger;
    wdpa_p_id: Attribute.String;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<'api::pa.pa', 'oneToOne', 'admin::user'> &
      Attribute.Private;
    updatedBy: Attribute.Relation<'api::pa.pa', 'oneToOne', 'admin::user'> &
      Attribute.Private;
  };
}

export interface ApiProtectionCoverageStatProtectionCoverageStat
  extends Schema.CollectionType {
  collectionName: 'protection_coverage_stats';
  info: {
    singularName: 'protection-coverage-stat';
    pluralName: 'protection-coverage-stats';
    displayName: 'Protection Coverage Stats';
    description: '';
  };
  options: {
    draftAndPublish: false;
  };
  attributes: {
    location: Attribute.Relation<
      'api::protection-coverage-stat.protection-coverage-stat',
      'manyToOne',
      'api::location.location'
    >;
    year: Attribute.Integer &
      Attribute.Required &
      Attribute.SetMinMax<{
        min: 0;
      }>;
    protected_area: Attribute.Decimal &
      Attribute.SetMinMax<{
        min: 0;
      }>;
    protected_areas_count: Attribute.Integer & Attribute.Required;
    environment: Attribute.Relation<
      'api::protection-coverage-stat.protection-coverage-stat',
      'oneToOne',
      'api::environment.environment'
    >;
    coverage: Attribute.Decimal;
    pas: Attribute.Decimal;
    oecms: Attribute.Decimal;
    is_last_year: Attribute.Boolean & Attribute.DefaultTo<false>;
    global_contribution: Attribute.Decimal;
    total_area: Attribute.BigInteger;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::protection-coverage-stat.protection-coverage-stat',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::protection-coverage-stat.protection-coverage-stat',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
  };
}

export interface ApiProtectionStatusProtectionStatus
  extends Schema.CollectionType {
  collectionName: 'protection_statuses';
  info: {
    singularName: 'protection-status';
    pluralName: 'protection-statuses';
    displayName: 'Protection Status';
    description: '';
  };
  options: {
    draftAndPublish: false;
  };
  pluginOptions: {
    i18n: {
      localized: true;
    };
  };
  attributes: {
    slug: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    name: Attribute.String &
      Attribute.Required &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    info: Attribute.Text &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::protection-status.protection-status',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::protection-status.protection-status',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    localizations: Attribute.Relation<
      'api::protection-status.protection-status',
      'oneToMany',
      'api::protection-status.protection-status'
    >;
    locale: Attribute.String;
  };
}

export interface ApiStaticIndicatorStaticIndicator
  extends Schema.CollectionType {
  collectionName: 'static_indicators';
  info: {
    singularName: 'static-indicator';
    pluralName: 'static-indicators';
    displayName: 'Static Indicators';
    description: '';
  };
  options: {
    draftAndPublish: true;
  };
  pluginOptions: {
    i18n: {
      localized: true;
    };
  };
  attributes: {
    slug: Attribute.String &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    source: Attribute.String &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: false;
        };
      }>;
    value: Attribute.String &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    description: Attribute.Text &
      Attribute.SetPluginOptions<{
        i18n: {
          localized: true;
        };
      }>;
    createdAt: Attribute.DateTime;
    updatedAt: Attribute.DateTime;
    publishedAt: Attribute.DateTime;
    createdBy: Attribute.Relation<
      'api::static-indicator.static-indicator',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    updatedBy: Attribute.Relation<
      'api::static-indicator.static-indicator',
      'oneToOne',
      'admin::user'
    > &
      Attribute.Private;
    localizations: Attribute.Relation<
      'api::static-indicator.static-indicator',
      'oneToMany',
      'api::static-indicator.static-indicator'
    >;
    locale: Attribute.String;
  };
}

declare module '@strapi/types' {
  export module Shared {
    export interface ContentTypes {
      'admin::permission': AdminPermission;
      'admin::user': AdminUser;
      'admin::role': AdminRole;
      'admin::api-token': AdminApiToken;
      'admin::api-token-permission': AdminApiTokenPermission;
      'admin::transfer-token': AdminTransferToken;
      'admin::transfer-token-permission': AdminTransferTokenPermission;
      'plugin::upload.file': PluginUploadFile;
      'plugin::upload.folder': PluginUploadFolder;
      'plugin::i18n.locale': PluginI18NLocale;
      'plugin::users-permissions.permission': PluginUsersPermissionsPermission;
      'plugin::users-permissions.role': PluginUsersPermissionsRole;
      'plugin::users-permissions.user': PluginUsersPermissionsUser;
      'api::contact-detail.contact-detail': ApiContactDetailContactDetail;
      'api::data-info.data-info': ApiDataInfoDataInfo;
      'api::data-source.data-source': ApiDataSourceDataSource;
      'api::data-tool.data-tool': ApiDataToolDataTool;
      'api::data-tool-ecosystem.data-tool-ecosystem': ApiDataToolEcosystemDataToolEcosystem;
      'api::data-tool-language.data-tool-language': ApiDataToolLanguageDataToolLanguage;
      'api::data-tool-resource-type.data-tool-resource-type': ApiDataToolResourceTypeDataToolResourceType;
      'api::dataset.dataset': ApiDatasetDataset;
      'api::environment.environment': ApiEnvironmentEnvironment;
      'api::feature-flag.feature-flag': ApiFeatureFlagFeatureFlag;
      'api::fishing-protection-level.fishing-protection-level': ApiFishingProtectionLevelFishingProtectionLevel;
      'api::fishing-protection-level-stat.fishing-protection-level-stat': ApiFishingProtectionLevelStatFishingProtectionLevelStat;
      'api::habitat.habitat': ApiHabitatHabitat;
      'api::habitat-stat.habitat-stat': ApiHabitatStatHabitatStat;
      'api::layer.layer': ApiLayerLayer;
      'api::location.location': ApiLocationLocation;
      'api::mpa-iucn-category.mpa-iucn-category': ApiMpaIucnCategoryMpaIucnCategory;
      'api::mpaa-establishment-stage.mpaa-establishment-stage': ApiMpaaEstablishmentStageMpaaEstablishmentStage;
      'api::mpaa-protection-level.mpaa-protection-level': ApiMpaaProtectionLevelMpaaProtectionLevel;
      'api::mpaa-protection-level-stat.mpaa-protection-level-stat': ApiMpaaProtectionLevelStatMpaaProtectionLevelStat;
      'api::pa.pa': ApiPaPa;
      'api::protection-coverage-stat.protection-coverage-stat': ApiProtectionCoverageStatProtectionCoverageStat;
      'api::protection-status.protection-status': ApiProtectionStatusProtectionStatus;
      'api::static-indicator.static-indicator': ApiStaticIndicatorStaticIndicator;
    }
  }
}
